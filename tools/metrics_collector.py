"""
Metrics Collector: Comprehensive Performance & Reliability Analytics

Collects metrics for:
- Per-tool success rates and retry patterns
- Per-category resolution effectiveness
- Confidence distribution
- Escalation analysis
- Response time analytics
"""

from typing import Dict, List, Any
from datetime import datetime
from collections import defaultdict
import json
import os

from tools.decision_utils import is_escalated_decision


class MetricsCollector:
    """Collects and analyzes agent performance metrics."""
    
    def __init__(self):
        self.tickets_processed = 0
        self.tickets_successful = 0
        self.tickets_escalated = 0
        
        self.per_category_metrics = defaultdict(lambda: {
            "count": 0,
            "successful": 0,
            "escalated": 0,
            "avg_confidence": 0.0,
            "avg_steps": 0,
            "avg_attempts": 0,
        })
        
        self.per_tool_metrics = defaultdict(lambda: {
            "calls": 0,
            "successful": 0,
            "failed": 0,
            "avg_attempts": 0.0,
            "total_attempts": 0,
        })
        
        self.confidence_distribution = defaultdict(int)
        self.response_times: List[float] = []
        self.escalation_reasons = defaultdict(int)
        
    def record_ticket(
        self,
        ticket_id: str,
        category: str,
        decision: str,
        confidence: float,
        reasoning_chain: List[Dict[str, Any]],
        duration: float
    ) -> None:
        """Record metrics for a processed ticket."""
        
        self.tickets_processed += 1
        if not is_escalated_decision(decision):
            self.tickets_successful += 1
        else:
            self.tickets_escalated += 1
        
        # Category metrics
        cat_metrics = self.per_category_metrics[category]
        cat_metrics["count"] += 1
        if not is_escalated_decision(decision):
            cat_metrics["successful"] += 1
        else:
            cat_metrics["escalated"] += 1
        
        # Aggregate confidence & steps
        num_steps = len(reasoning_chain)
        # attempts can be either an int or a list of attempt records
        total_attempts = 0
        for s in reasoning_chain:
            attempts_val = s.get("attempts", 1)
            # Handle both scalar (int) and list (detailed attempts)
            if isinstance(attempts_val, list):
                total_attempts += len(attempts_val)
            else:
                total_attempts += attempts_val
        
        cat_metrics["avg_confidence"] = (
            (cat_metrics["avg_confidence"] * (cat_metrics["count"] - 1) + confidence) /
            cat_metrics["count"]
        )
        cat_metrics["avg_steps"] = (
            (cat_metrics["avg_steps"] * (cat_metrics["count"] - 1) + num_steps) /
            cat_metrics["count"]
        )
        cat_metrics["avg_attempts"] = (
            (cat_metrics["avg_attempts"] * (cat_metrics["count"] - 1) + total_attempts) /
            cat_metrics["count"]
        )
        
        # Tool metrics from reasoning chain
        for step in reasoning_chain:
            tool_name = step.get("action", "unknown")
            attempts_val = step.get("attempts", 1)
            # Handle both scalar and list attempts
            if isinstance(attempts_val, list):
                attempts_count = len(attempts_val)
            else:
                attempts_count = attempts_val
            status = step.get("status", "unknown")
            
            tool_metrics = self.per_tool_metrics[tool_name]
            tool_metrics["calls"] += 1
            tool_metrics["total_attempts"] += attempts_count
            tool_metrics["avg_attempts"] = tool_metrics["total_attempts"] / tool_metrics["calls"]
            
            if status == "success":
                tool_metrics["successful"] += 1
            else:
                tool_metrics["failed"] += 1
        
        # Confidence distribution (bucket into 10% ranges)
        confidence_bucket = int(confidence * 10)
        self.confidence_distribution[confidence_bucket] += 1
        
        # Response time tracking
        self.response_times.append(duration)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        avg_response_time = (
            sum(self.response_times) / len(self.response_times)
            if self.response_times else 0.0
        )
        
        return {
            "batch_summary": {
                "total_processed": self.tickets_processed,
                "successful": self.tickets_successful,
                "escalated": self.tickets_escalated,
                "success_rate": (
                    self.tickets_successful / self.tickets_processed
                    if self.tickets_processed > 0 else 0.0
                ),
                "escalation_rate": (
                    self.tickets_escalated / self.tickets_processed
                    if self.tickets_processed > 0 else 0.0
                ),
                "avg_response_time": round(avg_response_time, 2),
                "min_response_time": min(self.response_times) if self.response_times else 0.0,
                "max_response_time": max(self.response_times) if self.response_times else 0.0,
            },
            "per_category": dict(self.per_category_metrics),
            "per_tool": dict(self.per_tool_metrics),
            "confidence_distribution": dict(sorted(self.confidence_distribution.items())),
        }
    
    def get_category_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed breakdown by ticket category."""
        breakdown = {}
        for category, metrics in self.per_category_metrics.items():
            if metrics["count"] > 0:
                breakdown[category] = {
                    "total": metrics["count"],
                    "successful": metrics["successful"],
                    "escalated": metrics["escalated"],
                    "success_rate": metrics["successful"] / metrics["count"],
                    "avg_confidence": round(metrics["avg_confidence"], 2),
                    "avg_steps": round(metrics["avg_steps"], 1),
                    "avg_attempts": round(metrics["avg_attempts"], 1),
                }
        return breakdown
    
    def get_tool_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed breakdown by tool used."""
        analysis = {}
        for tool_name, metrics in self.per_tool_metrics.items():
            if metrics["calls"] > 0:
                analysis[tool_name] = {
                    "total_calls": metrics["calls"],
                    "successful": metrics["successful"],
                    "failed": metrics["failed"],
                    "success_rate": metrics["successful"] / metrics["calls"],
                    "avg_attempts_per_call": round(metrics["avg_attempts"], 2),
                }
        return analysis
    
    def get_confidence_stats(self) -> Dict[str, Any]:
        """Get confidence score distribution stats."""
        if not self.confidence_distribution:
            return {}
        
        all_scores = []
        for bucket, count in self.confidence_distribution.items():
            # Reconstruct approximate scores from buckets
            for _ in range(count):
                all_scores.append(bucket / 10.0)
        
        if not all_scores:
            return {}
        
        all_scores.sort()
        
        return {
            "min": min(all_scores),
            "max": max(all_scores),
            "mean": sum(all_scores) / len(all_scores),
            "median": all_scores[len(all_scores) // 2],
            "distribution": dict(self.confidence_distribution),
        }
    
    def export_metrics(self, filepath: str = "logs/metrics.json") -> None:
        """Export all metrics to JSON for external analysis."""
        metrics_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": self.get_summary(),
            "category_breakdown": self.get_category_breakdown(),
            "tool_analysis": self.get_tool_analysis(),
            "confidence_stats": self.get_confidence_stats(),
        }
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(metrics_data, f, indent=2)

