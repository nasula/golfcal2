"""
Utility functions and decorators for CLI argument handling.
"""

import argparse
from functools import wraps
from typing import Callable, Optional, List, Union, Any, Dict, Type
from dataclasses import dataclass
from enum import Enum, auto
import logging
from golfcal2.config.settings import AppConfig

@dataclass
class CLIContext:
    """Context object for CLI command execution."""
    args: argparse.Namespace
    logger: logging.Logger
    config: AppConfig
    parser: argparse.ArgumentParser

class CommandCategory(Enum):
    """Categories for organizing commands."""
    PROCESS = auto()
    LIST = auto()
    GET = auto()
    CHECK = auto()
    MANAGE = auto()

@dataclass
class CommandMetadata:
    """Metadata for command registration."""
    name: str
    help_text: str
    category: CommandCategory
    handler: Callable[[CLIContext], int]
    options: List[Dict[str, Any]]
    parent_command: Optional[str] = None

class CLIOptionFactory:
    """Factory for creating common CLI options with consistent validation."""
    
    @staticmethod
    def create_format_option() -> Dict[str, Any]:
        return {
            'name': '--format',
            'choices': ['text', 'json'],
            'default': 'text',
            'help': 'Output format: human-readable text or machine-readable JSON (default: text)'
        }
    
    @staticmethod
    def create_weather_service_option() -> Dict[str, Any]:
        return {
            'name': '--service',
            'choices': ['met', 'portuguese', 'iberian'],
            'help': 'Weather service to use (met=MET.no for Nordic countries, portuguese=IPMA for Portugal, iberian=AEMET for Spain)'
        }
    
    @staticmethod
    def create_location_options() -> List[Dict[str, Any]]:
        return [
            {
                'name': '--lat',
                'type': float,
                'required': True,
                'help': 'Latitude of the location',
                'validator': lambda x: -90 <= x <= 90
            },
            {
                'name': '--lon',
                'type': float,
                'required': True,
                'help': 'Longitude of the location',
                'validator': lambda x: -180 <= x <= 180
            }
        ]
    
    @staticmethod
    def create_date_option() -> Dict[str, Any]:
        return {
            'name': '--date',
            'help': 'Date in YYYY-MM-DD format',
            'validator': lambda x: len(x.split('-')) == 3
        }

class CommandRegistry:
    """Registry for CLI commands with metadata."""
    
    _commands: Dict[str, CommandMetadata] = {}
    _categories: Dict[CommandCategory, List[str]] = {}
    _parent_commands: Dict[str, List[str]] = {}
    
    @classmethod
    def register(cls, 
                name: str,
                help_text: str,
                category: CommandCategory,
                options: Optional[List[Dict[str, Any]]] = None,
                parent_command: Optional[str] = None) -> Callable:
        """Decorator to register a command handler."""
        def decorator(handler: Callable) -> Callable:
            metadata = CommandMetadata(
                name=name,
                help_text=help_text,
                category=category,
                handler=handler,
                options=options or [],
                parent_command=parent_command
            )
            cls._commands[name] = metadata
            
            if category not in cls._categories:
                cls._categories[category] = []
            cls._categories[category].append(name)
            
            if parent_command:
                if parent_command not in cls._parent_commands:
                    cls._parent_commands[parent_command] = []
                cls._parent_commands[parent_command].append(name)
            
            return handler
        return decorator
    
    @classmethod
    def get_command(cls, name: str) -> Optional[CommandMetadata]:
        """Get command metadata by name."""
        return cls._commands.get(name)
    
    @classmethod
    def get_category_commands(cls, category: CommandCategory) -> List[str]:
        """Get all commands in a category."""
        return cls._categories.get(category, [])
    
    @classmethod
    def get_subcommands(cls, parent_command: str) -> List[str]:
        """Get all subcommands for a parent command."""
        return cls._parent_commands.get(parent_command, [])

class ArgumentValidator:
    """Validator for CLI arguments."""
    
    @staticmethod
    def validate_option(option: Dict[str, Any], value: Any) -> bool:
        """Validate a single option value."""
        if 'validator' not in option:
            return True
            
        try:
            return option['validator'](value)
        except Exception:
            return False
    
    @staticmethod
    def validate_args(args: argparse.Namespace, command: CommandMetadata) -> List[str]:
        """Validate all arguments for a command."""
        errors = []
        
        for option in command.options:
            value = getattr(args, option['name'].lstrip('-').replace('-', '_'), None)
            if value is not None and not ArgumentValidator.validate_option(option, value):
                errors.append(f"Invalid value for {option['name']}: {value}")
        
        return errors

def add_common_options(parser: argparse.ArgumentParser) -> None:
    """Add common global options to a parser."""
    parser.add_argument(
        '-u', '--user',
        help='Process specific user only (default: process all configured users)'
    )
    parser.add_argument(
        '--dev',
        action='store_true',
        help='Run in development mode with additional debug output and test data'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging output'
    )
    parser.add_argument(
        '--log-file',
        help='Path to write log output (default: logs to stdout)'
    )

def with_common_options(func: Callable) -> Callable:
    """Decorator to add common options to a command function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        parser = args[0] if args else kwargs.get('parser')
        if parser and isinstance(parser, argparse.ArgumentParser):
            add_common_options(parser)
        return func(*args, **kwargs)
    return wrapper

class CLIBuilder:
    """Builder for constructing CLI parsers with consistent formatting."""
    
    # Custom option fields that should not be passed to argparse
    _CUSTOM_FIELDS = {'validator'}
    
    def __init__(self, description: str):
        self.parser = argparse.ArgumentParser(
            description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter
        )
        self.subparsers = self.parser.add_subparsers(dest='command', title='commands')
        self.command_groups = {}

    def add_command(self, command: CommandMetadata) -> None:
        """Add a command to the CLI with proper parent/child relationships."""
        # Create parent group if needed
        if command.parent_command:
            if command.parent_command not in self.command_groups:
                parent_parser = self.subparsers.add_parser(
                    command.parent_command,
                    help=f"{command.parent_command.capitalize()} commands"
                )
                subcommands = CommandRegistry.get_subcommands(command.parent_command)
                self.command_groups[command.parent_command] = parent_parser.add_subparsers(
                    title=f"{command.parent_command} commands",
                    dest=f"{command.parent_command}_subcommand",
                    required=True,
                    help=f"Available {command.parent_command} commands: {', '.join(subcommands)}"
                )
            
            # Add to parent's subparsers
            parser = self.command_groups[command.parent_command].add_parser(
                command.name,
                help=command.help_text
            )
        else:
            # Add to root commands
            parser = self.subparsers.add_parser(
                command.name,
                help=command.help_text
            )

        # Add command options
        for option in command.options:
            # Make a copy of the option dict to avoid modifying the original
            option_copy = option.copy()
            name = option_copy.pop('name')
            # Create a copy of the option dict without custom fields
            argparse_options = {k: v for k, v in option_copy.items() 
                              if k not in self._CUSTOM_FIELDS}
            parser.add_argument(name, **argparse_options)
    
    def build(self) -> argparse.ArgumentParser:
        """Build and return the complete parser."""
        return self.parser

def create_command_group(name: str, help_text: str) -> Callable:
    """Decorator to create a command group."""
    def decorator(cls: Type) -> Type:
        setattr(cls, '_command_group', name)
        setattr(cls, '_command_help', help_text)
        return cls
    return decorator

# ... rest of the file ... 