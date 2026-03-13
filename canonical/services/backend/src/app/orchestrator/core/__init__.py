"""
Core Orchestrator Module

This module provides the main orchestrator functionality for cell workflow execution.
It is organized into specialized submodules:

- state_manager.py: Handles cell state transitions and updates
- workflow_executor.py: Manages workflow execution strategies
- monitoring.py: Handles queue monitoring and processing control
- orchestrator.py: Main facade class that unifies all functionality

Public API:
    Orchestrator: Main orchestrator class for workflow execution
"""

from .orchestrator import Orchestrator

__all__ = ["Orchestrator"]
