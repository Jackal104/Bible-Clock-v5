#!/usr/bin/env python3
"""
Time-based Data Aggregator for Bible Clock v5
Aggregates daily metrics into weekly, monthly, yearly, and all-time summaries.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import calendar

logger = logging.getLogger(__name__)

@dataclass
class TimeAggregatedMetrics:
    """Aggregated metrics for different time periods."""
    period_type: str  # 'daily', 'weekly', 'monthly', 'yearly', 'all_time'
    period_key: str   # '2025-08-27', '2025-W35', '2025-08', '2025', 'all_time'
    start_date: str
    end_date: str
    total_conversations: int
    categories: Dict[str, int]
    keywords: Dict[str, int]
    avg_response_time: float
    success_rate: float
    hourly_distribution: Dict[int, int]
    daily_breakdown: Dict[str, int]  # For weekly/monthly - shows daily counts
    translation_usage: Dict[str, int] = None  # New: track translation usage
    bible_books_accessed: Dict[str, int] = None  # New: track Bible book access
    
class TimeAggregator:
    """Handles aggregation of daily metrics into different time periods."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths for different aggregation levels
        self.daily_file = self.data_dir / "aggregated_metrics.json"
        self.weekly_file = self.data_dir / "weekly_metrics.json"
        self.monthly_file = self.data_dir / "monthly_metrics.json"
        self.yearly_file = self.data_dir / "yearly_metrics.json"
        self.all_time_file = self.data_dir / "all_time_metrics.json"
        
        # Load existing data
        self.daily_data = {}
        self.weekly_data = {}
        self.monthly_data = {}
        self.yearly_data = {}
        self.all_time_data = {}
        
        self.load_all_data()
    
    def load_all_data(self):
        """Load all existing aggregated data."""
        try:
            # Load daily data (existing format)
            if self.daily_file.exists():
                with open(self.daily_file, 'r') as f:
                    self.daily_data = json.load(f)
            
            # Load weekly data
            if self.weekly_file.exists():
                with open(self.weekly_file, 'r') as f:
                    weekly_raw = json.load(f)
                    self.weekly_data = {
                        key: TimeAggregatedMetrics(**data)
                        for key, data in weekly_raw.items()
                    }
            
            # Load monthly data
            if self.monthly_file.exists():
                with open(self.monthly_file, 'r') as f:
                    monthly_raw = json.load(f)
                    self.monthly_data = {
                        key: TimeAggregatedMetrics(**data)
                        for key, data in monthly_raw.items()
                    }
            
            # Load yearly data
            if self.yearly_file.exists():
                with open(self.yearly_file, 'r') as f:
                    yearly_raw = json.load(f)
                    self.yearly_data = {
                        key: TimeAggregatedMetrics(**data)
                        for key, data in yearly_raw.items()
                    }
            
            # Load all-time data
            if self.all_time_file.exists():
                with open(self.all_time_file, 'r') as f:
                    all_time_raw = json.load(f)
                    if all_time_raw:
                        self.all_time_data = {
                            'all_time': TimeAggregatedMetrics(**all_time_raw['all_time'])
                        }
            
            logger.info(f"Loaded aggregated data: {len(self.daily_data)} daily, {len(self.weekly_data)} weekly, {len(self.monthly_data)} monthly, {len(self.yearly_data)} yearly")
            
        except Exception as e:
            logger.error(f"Error loading aggregated data: {e}")
    
    def save_all_data(self):
        """Save all aggregated data to files."""
        try:
            # Save daily data (keep existing format)
            with open(self.daily_file, 'w') as f:
                json.dump(self.daily_data, f, indent=2)
            
            # Save weekly data
            weekly_serializable = {
                key: asdict(metrics) for key, metrics in self.weekly_data.items()
            }
            with open(self.weekly_file, 'w') as f:
                json.dump(weekly_serializable, f, indent=2)
            
            # Save monthly data
            monthly_serializable = {
                key: asdict(metrics) for key, metrics in self.monthly_data.items()
            }
            with open(self.monthly_file, 'w') as f:
                json.dump(monthly_serializable, f, indent=2)
            
            # Save yearly data
            yearly_serializable = {
                key: asdict(metrics) for key, metrics in self.yearly_data.items()
            }
            with open(self.yearly_file, 'w') as f:
                json.dump(yearly_serializable, f, indent=2)
            
            # Save all-time data
            if self.all_time_data:
                all_time_serializable = {
                    key: asdict(metrics) for key, metrics in self.all_time_data.items()
                }
                with open(self.all_time_file, 'w') as f:
                    json.dump(all_time_serializable, f, indent=2)
            
            logger.info("All aggregated data saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving aggregated data: {e}")
    
    def get_week_key(self, date_str: str) -> str:
        """Get ISO week key (e.g., '2025-W35') from date string."""
        date_obj = datetime.fromisoformat(date_str).date()
        year, week, _ = date_obj.isocalendar()
        return f"{year}-W{week:02d}"
    
    def get_week_dates(self, week_key: str) -> tuple[str, str]:
        """Get start and end dates for a week key."""
        year, week = week_key.split('-W')
        year = int(year)
        week = int(week)
        
        # Get the Monday of the specified week
        jan4 = datetime(year, 1, 4).date()
        week_start = jan4 - timedelta(days=jan4.weekday()) + timedelta(weeks=week-1)
        week_end = week_start + timedelta(days=6)
        
        return week_start.isoformat(), week_end.isoformat()
    
    def get_month_key(self, date_str: str) -> str:
        """Get month key (e.g., '2025-08') from date string."""
        date_obj = datetime.fromisoformat(date_str).date()
        return f"{date_obj.year}-{date_obj.month:02d}"
    
    def get_month_dates(self, month_key: str) -> tuple[str, str]:
        """Get start and end dates for a month key."""
        year, month = month_key.split('-')
        year, month = int(year), int(month)
        
        start_date = datetime(year, month, 1).date()
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime(year, month, last_day).date()
        
        return start_date.isoformat(), end_date.isoformat()
    
    def get_year_key(self, date_str: str) -> str:
        """Get year key (e.g., '2025') from date string."""
        date_obj = datetime.fromisoformat(date_str).date()
        return str(date_obj.year)
    
    def get_year_dates(self, year_key: str) -> tuple[str, str]:
        """Get start and end dates for a year key."""
        year = int(year_key)
        start_date = datetime(year, 1, 1).date()
        end_date = datetime(year, 12, 31).date()
        return start_date.isoformat(), end_date.isoformat()
    
    def aggregate_period_data(self, daily_data_subset: Dict[str, Any], 
                            period_type: str, period_key: str,
                            start_date: str, end_date: str) -> TimeAggregatedMetrics:
        """Aggregate daily data into a time period."""
        if not daily_data_subset:
            return TimeAggregatedMetrics(
                period_type=period_type,
                period_key=period_key,
                start_date=start_date,
                end_date=end_date,
                total_conversations=0,
                categories={},
                keywords={},
                avg_response_time=0.0,
                success_rate=100.0,
                hourly_distribution={},
                daily_breakdown={}
            )
        
        # Aggregate all metrics
        total_conversations = 0
        combined_categories = defaultdict(int)
        combined_keywords = defaultdict(int)
        combined_hourly = defaultdict(int)
        total_weighted_response_time = 0
        total_weighted_success = 0
        daily_breakdown = {}
        
        for date_str, day_data in daily_data_subset.items():
            conversations = day_data.get('total_conversations', 0)
            total_conversations += conversations
            daily_breakdown[date_str] = conversations
            
            # Categories
            for category, count in day_data.get('categories', {}).items():
                combined_categories[category] += count
            
            # Keywords
            for keyword, count in day_data.get('keywords', {}).items():
                combined_keywords[keyword] += count
            
            # Hourly distribution
            for hour, count in day_data.get('hourly_distribution', {}).items():
                combined_hourly[int(hour)] += count
            
            # Weighted averages
            if conversations > 0:
                total_weighted_response_time += day_data.get('avg_response_time', 0) * conversations
                total_weighted_success += (day_data.get('success_rate', 100) / 100) * conversations
        
        # Calculate final metrics
        avg_response_time = (total_weighted_response_time / total_conversations 
                           if total_conversations > 0 else 0.0)
        success_rate = (total_weighted_success / total_conversations * 100 
                       if total_conversations > 0 else 100.0)
        
        return TimeAggregatedMetrics(
            period_type=period_type,
            period_key=period_key,
            start_date=start_date,
            end_date=end_date,
            total_conversations=total_conversations,
            categories=dict(combined_categories),
            keywords=dict(Counter(combined_keywords).most_common(20)),
            avg_response_time=round(avg_response_time, 2),
            success_rate=round(success_rate, 1),
            hourly_distribution=dict(combined_hourly),
            daily_breakdown=daily_breakdown
        )
    
    def update_all_aggregations(self):
        """Update all time-based aggregations from daily data."""
        if not self.daily_data:
            logger.warning("No daily data found for aggregation")
            return
        
        # Get all dates to process
        all_dates = sorted(self.daily_data.keys())
        
        # Update weekly aggregations
        weekly_groups = defaultdict(dict)
        for date_str in all_dates:
            week_key = self.get_week_key(date_str)
            weekly_groups[week_key][date_str] = self.daily_data[date_str]
        
        for week_key, week_data in weekly_groups.items():
            start_date, end_date = self.get_week_dates(week_key)
            self.weekly_data[week_key] = self.aggregate_period_data(
                week_data, 'weekly', week_key, start_date, end_date
            )
        
        # Update monthly aggregations
        monthly_groups = defaultdict(dict)
        for date_str in all_dates:
            month_key = self.get_month_key(date_str)
            monthly_groups[month_key][date_str] = self.daily_data[date_str]
        
        for month_key, month_data in monthly_groups.items():
            start_date, end_date = self.get_month_dates(month_key)
            self.monthly_data[month_key] = self.aggregate_period_data(
                month_data, 'monthly', month_key, start_date, end_date
            )
        
        # Update yearly aggregations
        yearly_groups = defaultdict(dict)
        for date_str in all_dates:
            year_key = self.get_year_key(date_str)
            yearly_groups[year_key][date_str] = self.daily_data[date_str]
        
        for year_key, year_data in yearly_groups.items():
            start_date, end_date = self.get_year_dates(year_key)
            self.yearly_data[year_key] = self.aggregate_period_data(
                year_data, 'yearly', year_key, start_date, end_date
            )
        
        # Update all-time aggregation
        if all_dates:
            start_date = min(all_dates)
            end_date = max(all_dates)
            self.all_time_data['all_time'] = self.aggregate_period_data(
                self.daily_data, 'all_time', 'all_time', start_date, end_date
            )
        
        logger.info(f"Updated aggregations: {len(self.weekly_data)} weeks, {len(self.monthly_data)} months, {len(self.yearly_data)} years")
    
    def get_filtered_data(self, time_filter: str, date_reference: str = None) -> Dict[str, Any]:
        """Get aggregated data for a specific time filter."""
        if date_reference is None:
            date_reference = datetime.now().date().isoformat()
        
        reference_date = datetime.fromisoformat(date_reference).date()
        
        if time_filter == 'today':
            date_key = reference_date.isoformat()
            return self.daily_data.get(date_key, {})
        
        elif time_filter == 'weekly':
            week_key = self.get_week_key(reference_date.isoformat())
            if week_key in self.weekly_data:
                return asdict(self.weekly_data[week_key])
            return {}
        
        elif time_filter == 'monthly':
            month_key = self.get_month_key(reference_date.isoformat())
            if month_key in self.monthly_data:
                return asdict(self.monthly_data[month_key])
            return {}
        
        elif time_filter == 'yearly':
            year_key = self.get_year_key(reference_date.isoformat())
            if year_key in self.yearly_data:
                return asdict(self.yearly_data[year_key])
            return {}
        
        elif time_filter == 'all_time':
            if 'all_time' in self.all_time_data:
                return asdict(self.all_time_data['all_time'])
            return {}
        
        else:
            logger.warning(f"Unknown time filter: {time_filter}")
            return {}
    
    def get_chart_data(self, time_filter: str, chart_type: str, 
                      date_reference: str = None) -> Dict[str, Any]:
        """Get chart data for specific time filter and chart type."""
        filtered_data = self.get_filtered_data(time_filter, date_reference)
        
        if not filtered_data:
            return {'labels': [], 'data': []}
        
        if chart_type == 'categories':
            categories = filtered_data.get('categories', {})
            return {
                'labels': list(categories.keys()),
                'data': list(categories.values())
            }
        
        elif chart_type == 'keywords':
            keywords = filtered_data.get('keywords', {})
            # Get top 10 keywords for chart
            sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:10]
            return {
                'labels': [kw[0] for kw in sorted_keywords],
                'data': [kw[1] for kw in sorted_keywords]
            }
        
        elif chart_type == 'hourly':
            hourly = filtered_data.get('hourly_distribution', {})
            # Ensure all 24 hours are represented
            hours = list(range(24))
            data = [hourly.get(str(hour), 0) for hour in hours]
            return {
                'labels': [f"{hour:02d}:00" for hour in hours],
                'data': data
            }
        
        elif chart_type == 'daily_trend' and time_filter in ['weekly', 'monthly']:
            daily_breakdown = filtered_data.get('daily_breakdown', {})
            sorted_days = sorted(daily_breakdown.items())
            return {
                'labels': [day[0] for day in sorted_days],
                'data': [day[1] for day in sorted_days]
            }
        
        else:
            logger.warning(f"Unknown chart type: {chart_type}")
            return {'labels': [], 'data': []}
    
    def refresh_aggregations(self):
        """Refresh all aggregations from daily data and save."""
        self.update_all_aggregations()
        self.save_all_data()
        logger.info("All aggregations refreshed and saved")