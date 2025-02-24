"""
Utility functions and decorators for CLI argument handling.
"""

import argparse
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from functools import wraps
from typing import Any, TypeVar, cast

from typing_extensions import ParamSpec

from golfcal2.config.types import AppConfig

T = TypeVar('T')
P = ParamSpec('P')
F = TypeVar('F', bound=Callable[..., Any])

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
    IMPORT = auto()

@dataclass
class CommandMetadata:
    """Metadata for command registration."""
    name: str
    help_text: str
    category: CommandCategory
    handler: Callable[[CLIContext], int]
    options: list[dict[str, Any]]
    parent_command: str | None = None

class CLIOptionFactory:
    """Factory for creating common CLI options with consistent validation."""
    
    @staticmethod
    def create_format_option() -> dict[str, Any]:
        return {
            'name': '--format',
            'choices': ['text', 'json'],
            'default': 'text',
            'help': 'Output format: human-readable text or machine-readable JSON (default: text)'
        }
    
    @staticmethod
    def create_weather_service_option() -> dict[str, Any]:
        return {
            'name': '--service',
            'choices': ['met', 'portuguese', 'iberian'],
            'help': 'Weather service to use (met=MET.no for Nordic countries, portuguese=IPMA for Portugal, iberian=AEMET for Spain)'
        }
    
    @staticmethod
    def create_location_options() -> list[dict[str, Any]]:
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
    def create_date_option() -> dict[str, Any]:
        return {
            'name': '--date',
            'help': 'Date in YYYY-MM-DD format',
            'validator': lambda x: len(x.split('-')) == 3
        }

class CommandRegistry:
    """Registry for CLI commands with metadata."""
    
    _commands: dict[str, CommandMetadata] = {}
    _categories: dict[CommandCategory, list[str]] = {}
    _parent_commands: dict[str, list[str]] = {}
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered commands."""
        cls._commands.clear()
        cls._categories.clear()
        cls._parent_commands.clear()

    @classmethod
    def register(cls, 
                name: str,
                help_text: str,
                category: CommandCategory,
                options: list[dict[str, Any]] | None = None,
                parent_command: str | None = None) -> Callable[[Callable[[CLIContext], int]], Callable[[CLIContext], int]]:
        """Register a command handler."""
        def decorator(handler: Callable[[CLIContext], int]) -> Callable[[CLIContext], int]:
            metadata = CommandMetadata(
                name=name,
                help_text=help_text,
                category=category,
                handler=handler,
                options=options or [],
                parent_command=parent_command
            )
            
            # Register the command
            cls._commands[name] = metadata
            
            # Register the command in its category
            if category not in cls._categories:
                cls._categories[category] = []
            if name not in cls._categories[category]:
                cls._categories[category].append(name)
            
            # Register the command as a subcommand if it has a parent
            if parent_command:
                if parent_command not in cls._parent_commands:
                    cls._parent_commands[parent_command] = []
                if name not in cls._parent_commands[parent_command]:
                    cls._parent_commands[parent_command].append(name)
                
                # If the parent command doesn't exist yet, create it
                if parent_command not in cls._commands:
                    parent_metadata = CommandMetadata(
                        name=parent_command,
                        help_text=f"{parent_command.capitalize()} commands",
                        category=category,
                        handler=lambda ctx: 0,  # Dummy handler for the parent command
                        options=[],
                        parent_command=None
                    )
                    cls._commands[parent_command] = parent_metadata
                    
                    # Register the parent command in its category
                    if category not in cls._categories:
                        cls._categories[category] = []
                    if parent_command not in cls._categories[category]:
                        cls._categories[category].append(parent_command)
            
            return handler
        return decorator
    
    @classmethod
    def get_command(cls, name: str) -> CommandMetadata | None:
        """Get command metadata by name."""
        return cls._commands.get(name)
    
    @classmethod
    def get_category_commands(cls, category: CommandCategory) -> list[str]:
        """Get all commands in a category."""
        return cls._categories.get(category, [])
    
    @classmethod
    def get_subcommands(cls, parent_command: str) -> list[str]:
        """Get all subcommands for a parent command."""
        return cls._parent_commands.get(parent_command, [])

class ArgumentValidator:
    """Validator for CLI arguments."""
    
    @staticmethod
    def validate_option(option: dict[str, Any], value: Any) -> bool:
        """Validate a single option value."""
        if 'validator' not in option:
            return True
            
        try:
            result = option['validator'](value)
            return bool(result)
        except Exception:
            return False
    
    @staticmethod
    def validate_args(args: argparse.Namespace, command: CommandMetadata) -> list[str]:
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

def with_common_options(func: F) -> F:
    """Decorator to add common options to a command function."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        parser = args[0] if args else kwargs.get('parser')
        if parser and isinstance(parser, argparse.ArgumentParser):
            add_common_options(parser)
        return func(*args, **kwargs)
    return cast(F, wrapper)

class CLIBuilder:
    """Builder for constructing CLI parsers with consistent formatting."""
    
    # Custom option fields that should not be passed to argparse
    _CUSTOM_FIELDS = {'validator'}
    
    def __init__(self, description: str):
        """Initialize CLI builder."""
        self.parser = argparse.ArgumentParser(description=description)
        self.subparsers = self.parser.add_subparsers(dest='command', required=True)
        self._parent_parsers: dict[str, argparse._SubParsersAction[Any]] = {}
        
        # Instance-based command storage
        self._commands: dict[str, CommandMetadata] = {}
        self._categories: dict[CommandCategory, list[str]] = {}
        self._parent_commands: dict[str, list[str]] = {}
        self._registered_subcommands: set[tuple[str, str]] = set()  # (parent, name) pairs
        
        # Add common options to root parser
        add_common_options(self.parser)
    
    def register_command(self, name: str, help_text: str, category: CommandCategory, 
                        handler: Callable[[CLIContext], int], options: list[dict[str, Any]] | None = None,
                        parent_command: str | None = None) -> None:
        """Register a command with the builder."""
        # For subcommands, check if this exact command is already registered
        if parent_command:
            if (parent_command, name) in self._registered_subcommands:
                return  # Skip duplicate subcommand registration
            self._registered_subcommands.add((parent_command, name))
        elif name in self._commands and not parent_command:
            return  # Skip duplicate top-level command registration
            
        cmd = CommandMetadata(
            name=name,
            help_text=help_text,
            category=category,
            handler=handler,
            options=options or [],
            parent_command=parent_command
        )
        
        self._commands[name] = cmd
        
        # Update category mapping
        if category not in self._categories:
            self._categories[category] = []
        if name not in self._categories[category]:
            self._categories[category].append(name)
        
        # Update parent command mapping
        if parent_command:
            if parent_command not in self._parent_commands:
                self._parent_commands[parent_command] = []
            if name not in self._parent_commands[parent_command]:
                self._parent_commands[parent_command].append(name)
            
        # Add command to parser
        try:
            self.add_command(cmd)
        except argparse.ArgumentError:
            # If we get an argument error, the command might already exist
            # This is fine, as we've already registered the metadata
            pass
    
    def add_command(self, command: CommandMetadata) -> None:
        """Add a command to the parser."""
        try:
            if command.parent_command:
                # This is a subcommand - find its parent parser
                if command.parent_command not in self._parent_parsers:
                    # Create parent parser if it doesn't exist
                    parent_parser = self.subparsers.add_parser(
                        command.parent_command,
                        help=f"{command.parent_command.capitalize()} commands"
                    )
                    parent_subparsers = parent_parser.add_subparsers(
                        dest=f"{command.parent_command}_subcommand",
                        required=True
                    )
                    self._parent_parsers[command.parent_command] = parent_subparsers
                
                # Add command to parent's subparsers
                parser = self._parent_parsers[command.parent_command].add_parser(
                    command.name,
                    help=command.help_text
                )
            else:
                # This is a top-level command
                parser = self.subparsers.add_parser(
                    command.name,
                    help=command.help_text
                )
            
            # Add command's options
            for option in command.options:
                # Skip if no name is provided
                if 'name' not in option:
                    continue
                    
                # Make a copy of the option dict to avoid modifying the original
                option_copy = option.copy()
                
                # Extract name and create option dict
                name = option_copy.pop('name')
                option_dict = {k: v for k, v in option_copy.items() if k not in self._CUSTOM_FIELDS}
                
                # Handle positional vs optional arguments
                if name.startswith('--'):
                    # Optional argument
                    parser.add_argument(name, **option_dict)
                else:
                    # Positional argument
                    option_dict['dest'] = name.lower().replace('-', '_')
                    parser.add_argument(name, **option_dict)
            
            # Store command handler
            parser.set_defaults(func=command.handler)
        except argparse.ArgumentError:
            # If we get an argument error, the command might already exist
            # This is fine, as we've already registered the metadata
            pass
    
    def get_command(self, name: str) -> CommandMetadata | None:
        """Get command metadata by name."""
        return self._commands.get(name)
    
    def get_category_commands(self, category: CommandCategory) -> list[str]:
        """Get all commands in a category."""
        return self._categories.get(category, [])
    
    def get_subcommands(self, parent_command: str) -> list[str]:
        """Get all subcommands for a parent command."""
        return self._parent_commands.get(parent_command, [])
    
    def build(self) -> argparse.ArgumentParser:
        """Build and return the parser."""
        return self.parser

def create_command_group(name: str, help_text: str, category: CommandCategory | None = None) -> Callable[[type[Any]], type[Any]]:
    """Create a command group decorator."""
    def decorator(cls: type[Any]) -> type[Any]:
        """Decorate a class to create a command group."""
        # Store the command group metadata for later registration
        cls._command_group_metadata = {
            'name': name,
            'help_text': help_text,
            'category': category or CommandCategory.PROCESS,  # Default to PROCESS if not specified
            'options': []
        }
        return cls
    return decorator

# Global CLI builder instance
_cli_builder: CLIBuilder | None = None

def get_cli_builder() -> CLIBuilder:
    """Get or create the CLI builder instance."""
    global _cli_builder
    if _cli_builder is None:
        _cli_builder = CLIBuilder("Golf calendar application")
    return _cli_builder

def register_command(name: str, help_text: str, category: CommandCategory, 
                    options: list[dict[str, Any]] | None = None,
                    parent_command: str | None = None) -> Callable[[Callable[[CLIContext], int]], Callable[[CLIContext], int]]:
    """Register a command with the CLI builder."""
    def decorator(handler: Callable[[CLIContext], int]) -> Callable[[CLIContext], int]:
        """Decorate a function to register it as a command."""
        builder = get_cli_builder()
        builder.register_command(
            name=name,
            help_text=help_text,
            category=category,
            handler=handler,
            options=options,
            parent_command=parent_command
        )
        return handler
    return decorator

# ... rest of the file ... 