"""Simple cron expression parser for scheduling."""

import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


class CronExpression:
    """Simple cron expression parser and evaluator.
    
    Supports basic cron format: minute hour day_of_month month day_of_week
    Examples:
    - "0 9 * * *" - daily at 9:00 AM
    - "30 14 * * 1" - every Monday at 2:30 PM
    - "0 */6 * * *" - every 6 hours
    - "0 0 1 * *" - monthly on the 1st at midnight
    """
    
    def __init__(self, expression: str):
        """Parse cron expression.
        
        Args:
            expression: Cron expression string (5 fields)
        """
        self.expression = expression.strip()
        parts = self.expression.split()
        
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression}. Expected 5 fields.")
        
        self.minute, self.hour, self.day, self.month, self.weekday = parts
        
        # Pre-parse for validation
        self._parse_field(self.minute, 0, 59, "minute")
        self._parse_field(self.hour, 0, 23, "hour")
        self._parse_field(self.day, 1, 31, "day")
        self._parse_field(self.month, 1, 12, "month")
        self._parse_field(self.weekday, 0, 6, "weekday")  # 0=Sunday
    
    def _parse_field(self, field: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """Parse a cron field into list of valid values."""
        if field == "*":
            return list(range(min_val, max_val + 1))
        
        values = []
        for part in field.split(","):
            if "/" in part:
                # Handle step values like */5 or 1-10/2
                range_part, step = part.split("/", 1)
                step = int(step)
                
                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-", 1))
                else:
                    start = end = int(range_part)
                
                values.extend(range(start, end + 1, step))
            
            elif "-" in part:
                # Handle ranges like 1-5
                start, end = map(int, part.split("-", 1))
                values.extend(range(start, end + 1))
            
            else:
                # Single value
                values.append(int(part))
        
        # Validate values
        for val in values:
            if not (min_val <= val <= max_val):
                raise ValueError(f"Invalid {field_name} value: {val} (must be {min_val}-{max_val})")
        
        return sorted(set(values))
    
    def get_next_execution(self, after: Optional[datetime] = None) -> datetime:
        """Get the next execution time after the given datetime.
        
        Args:
            after: Reference datetime (default: now)
            
        Returns:
            Next execution datetime
        """
        if after is None:
            after = datetime.now()
        
        # Start from the next minute
        next_time = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
        
        # Get valid values for each field
        valid_minutes = self._parse_field(self.minute, 0, 59, "minute")
        valid_hours = self._parse_field(self.hour, 0, 23, "hour")
        valid_days = self._parse_field(self.day, 1, 31, "day")
        valid_months = self._parse_field(self.month, 1, 12, "month")
        valid_weekdays = self._parse_field(self.weekday, 0, 6, "weekday")
        
        # Find next valid time (with safety limit)
        for _ in range(366 * 24 * 60):  # Max 1 year of minutes
            if (next_time.minute in valid_minutes and
                next_time.hour in valid_hours and
                next_time.day in valid_days and
                next_time.month in valid_months and
                next_time.weekday() in valid_weekdays):
                return next_time
            
            next_time += timedelta(minutes=1)
        
        raise RuntimeError(f"Could not find next execution time for: {self.expression}")
    
    def should_run_at(self, dt: datetime) -> bool:
        """Check if the job should run at the given datetime.
        
        Args:
            dt: Datetime to check
            
        Returns:
            True if job should run at this time
        """
        try:
            valid_minutes = self._parse_field(self.minute, 0, 59, "minute")
            valid_hours = self._parse_field(self.hour, 0, 23, "hour")
            valid_days = self._parse_field(self.day, 1, 31, "day")
            valid_months = self._parse_field(self.month, 1, 12, "month")
            valid_weekdays = self._parse_field(self.weekday, 0, 6, "weekday")
            
            return (dt.minute in valid_minutes and
                   dt.hour in valid_hours and
                   dt.day in valid_days and
                   dt.month in valid_months and
                   dt.weekday() in valid_weekdays)
        except Exception:
            return False
    
    def __str__(self) -> str:
        return self.expression


def parse_cron_expression(expression: str) -> CronExpression:
    """Parse a cron expression string.
    
    Args:
        expression: Cron expression
        
    Returns:
        Parsed CronExpression object
    """
    return CronExpression(expression)