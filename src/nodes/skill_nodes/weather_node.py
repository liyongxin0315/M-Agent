"""
Weather Node - 天气查询节点

集成 weather 技能，提供天气查询能力。
"""

import logging
from typing import Any, Dict, Optional

from ..base_node import BaseNode, NodeResult, NodeStatus

logger = logging.getLogger(__name__)


class WeatherNode(BaseNode):
    """天气查询节点"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("weather", config)
        self._default_units = config.get("units", "metric") if config else "metric"
    
    async def execute(self, context: Dict[str, Any]) -> NodeResult:
        """
        执行天气查询
        
        Args:
            context: 执行上下文，包含:
                - location: 地点
                - days: 预报天数
                - units: 单位 (metric/imperial)
        
        Returns:
            NodeResult: 天气信息
        """
        try:
            location = context.get("location")
            days = context.get("days", 3)
            units = context.get("units", self._default_units)
            
            if not location:
                return NodeResult(
                    status=NodeStatus.FAILED,
                    error="缺少必需参数：location",
                    node_name=self.name
                )
            
            # 调用 weather 技能
            result = await self._get_weather(
                location=location,
                days=days,
                units=units
            )
            
            return NodeResult(
                status=NodeStatus.COMPLETED,
                output=result,
                node_name=self.name
            )
        
        except Exception as e:
            logger.error(f"天气查询失败：{e}")
            return NodeResult(
                status=NodeStatus.FAILED,
                error=str(e),
                node_name=self.name
            )
    
    async def _get_weather(
        self,
        location: str,
        days: int = 3,
        units: str = "metric"
    ) -> Dict[str, Any]:
        """
        获取天气信息
        
        使用 wttr.in 或 Open-Meteo API
        """
        import requests
        from datetime import datetime, timedelta
        
        # 使用 wttr.in API
        wttr_url = f"https://wttr.in/{location}?format=j1"
        
        try:
            response = requests.get(wttr_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # 解析当前天气
            current = data.get("current_condition", [{}])[0]
            
            # 解析预报
            forecast = []
            for day in data.get("weather", [])[:days]:
                forecast.append({
                    "date": day.get("date"),
                    "max_temp": day.get("maxtempC" if units == "metric" else "maxtempF"),
                    "min_temp": day.get("mintempC" if units == "metric" else "mintempF"),
                    "condition": day.get("avgDesc", [{}])[0] if day.get("avgDesc") else {},
                    "chance_of_rain": day.get("chanceofrain", "0"),
                    "humidity": day.get("avgHumidity", "0"),
                    "wind_speed": day.get("avgWindspeedKmph" if units == "metric" else "avgWindspeedMiles"),
                })
            
            return {
                "location": location,
                "current": {
                    "temp": current.get("temp_C" if units == "metric" else "temp_F"),
                    "condition": current.get("weatherDesc", [{}])[0].get("value", ""),
                    "humidity": current.get("humidity", ""),
                    "wind_speed": current.get("windspeedKmph" if units == "metric" else "windspeedMiles"),
                    "feels_like": current.get("FeelsLikeC" if units == "metric" else "FeelsLikeF"),
                    "updated": datetime.now().isoformat()
                },
                "forecast": forecast,
                "units": units
            }
        
        except Exception as e:
            logger.warning(f"wttr.in API 失败，尝试 Open-Meteo: {e}")
            return await self._get_weather_open_meteo(location, days, units)
    
    async def _get_weather_open_meteo(
        self,
        location: str,
        days: int,
        units: str
    ) -> Dict[str, Any]:
        """
        使用 Open-Meteo API 获取天气（降级方案）
        """
        import requests
        
        # 首先需要地理编码获取经纬度
        geocode_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
        
        try:
            geo_response = requests.get(geocode_url, timeout=30)
            geo_response.raise_for_status()
            geo_data = geo_response.json()
            
            if not geo_data.get("results"):
                raise ValueError(f"未找到地点：{location}")
            
            result = geo_data["results"][0]
            latitude = result["latitude"]
            longitude = result["longitude"]
            name = result["name"]
            
            # 获取天气预报
            forecast_url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={latitude}&longitude={longitude}"
                f"&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
                f"&current_weather=true"
                f"&forecast_days={days}"
            )
            
            forecast_response = requests.get(forecast_url, timeout=30)
            forecast_response.raise_for_status()
            forecast_data = forecast_response.json()
            
            # 解析当前天气
            current_weather = forecast_data.get("current_weather", {})
            
            # 解析预报
            daily = forecast_data.get("daily", {})
            forecast = []
            
            for i in range(len(daily.get("time", []))):
                forecast.append({
                    "date": daily["time"][i],
                    "max_temp": daily["temperature_2m_max"][i],
                    "min_temp": daily["temperature_2m_min"][i],
                    "precipitation_probability": daily["precipitation_probability_max"][i],
                    "weather_code": daily["weather_code"][i]
                })
            
            return {
                "location": name,
                "coordinates": {"lat": latitude, "lon": longitude},
                "current": {
                    "temp": current_weather.get("temperature"),
                    "wind_speed": current_weather.get("windspeed"),
                    "wind_direction": current_weather.get("winddirection"),
                    "weather_code": current_weather.get("weathercode"),
                    "updated": current_weather.get("time", "")
                },
                "forecast": forecast,
                "units": "metric"  # Open-Meteo 默认使用摄氏度
            }
        
        except Exception as e:
            raise RuntimeError(f"天气查询失败：{e}")
    
    def get_schema(self) -> Dict[str, Any]:
        """返回节点输入输出 schema"""
        return {
            "inputs": {
                "location": {"type": "string", "required": True, "description": "地点名称"},
                "days": {"type": "integer", "required": False, "default": 3, "minimum": 1, "maximum": 14},
                "units": {
                    "type": "string",
                    "required": False,
                    "default": "metric",
                    "enum": ["metric", "imperial"]
                }
            },
            "outputs": {
                "weather_info": {"type": "object", "description": "天气信息"}
            }
        }
