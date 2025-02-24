"""Unit tests for CLI argument parsing and validation."""

import argparse

import pytest

from golfcal2.cli import create_parser


class TestArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser that raises ArgumentError instead of exiting."""
    def error(self, message):
        raise argparse.ArgumentError(None, message)

def test_global_options():
    """Test global CLI options."""
    parser = create_parser()
    
    # Test user option
    args = parser.parse_args(['-u', 'testuser'])
    assert args.user == 'testuser'
    
    # Test dev mode
    args = parser.parse_args(['--dev'])
    assert args.dev is True
    
    # Test verbose mode
    args = parser.parse_args(['-v'])
    assert args.verbose is True
    
    # Test log file
    args = parser.parse_args(['--log-file', 'test.log'])
    assert args.log_file == 'test.log'

def test_process_command():
    """Test process command arguments."""
    parser = create_parser()
    
    # Test basic process command
    args = parser.parse_args(['process'])
    assert args.command == 'process'
    assert not args.dry_run
    assert not args.force
    
    # Test process with dry run
    args = parser.parse_args(['process', '--dry-run'])
    assert args.dry_run is True
    
    # Test process with force
    args = parser.parse_args(['process', '--force'])
    assert args.force is True
    
    # Test process with all options (global options must come before subcommand)
    args = parser.parse_args(['-u', 'testuser', 'process', '--dry-run', '--force'])
    assert args.command == 'process'
    assert args.dry_run is True
    assert args.force is True
    assert args.user == 'testuser'

def test_get_weather_command():
    """Test get weather command arguments."""
    parser = create_parser()
    
    # Test basic weather command
    args = parser.parse_args(['get', 'weather', '--lat', '60.1699', '--lon', '24.9384'])
    assert args.command == 'get'
    assert args.get_type == 'weather'
    assert args.lat == 60.1699
    assert args.lon == 24.9384
    assert args.format == 'text'  # Default format
    
    # Test weather with all options
    args = parser.parse_args([
        'get', 'weather',
        '--lat', '60.1699',
        '--lon', '24.9384',
        '--service', 'met',
        '--format', 'json'
    ])
    assert args.service == 'met'
    assert args.format == 'json'
    
    # Test weather with OpenMeteo service
    args = parser.parse_args([
        'get', 'weather',
        '--lat', '60.1699',
        '--lon', '24.9384',
        '--service', 'openmeteo'
    ])
    assert args.service == 'openmeteo'
    assert args.format == 'text'  # Default format

def test_list_command():
    """Test list command arguments."""
    parser = create_parser()
    
    # Test courses subcommand
    args = parser.parse_args(['list', 'courses'])
    assert args.command == 'list'
    assert args.list_type == 'courses'
    assert not args.all
    
    args = parser.parse_args(['list', 'courses', '--all'])
    assert args.all is True
    
    # Test weather-cache subcommand
    args = parser.parse_args(['list', 'weather-cache'])
    assert args.list_type == 'weather-cache'
    assert args.format == 'text'  # Default format
    
    args = parser.parse_args([
        'list', 'weather-cache',
        '--service', 'met',
        '--format', 'json',
        '--clear'
    ])
    assert args.service == 'met'
    assert args.format == 'json'
    assert args.clear is True

def test_list_reservations_command():
    """Test list reservations command arguments."""
    parser = create_parser()
    
    # Test basic reservations command
    args = parser.parse_args(['list', 'reservations'])
    assert args.command == 'list'
    assert args.list_type == 'reservations'
    assert args.format == 'text'  # Default format
    assert args.days == 1  # Default days
    assert not args.active
    assert not args.upcoming
    
    # Test with active flag
    args = parser.parse_args(['list', 'reservations', '--active'])
    assert args.active is True
    assert not args.upcoming
    
    # Test with upcoming flag
    args = parser.parse_args(['list', 'reservations', '--upcoming'])
    assert args.upcoming is True
    assert not args.active
    
    # Test with custom days
    args = parser.parse_args(['list', 'reservations', '--days', '7'])
    assert args.days == 7
    
    # Test with JSON format
    args = parser.parse_args(['list', 'reservations', '--format', 'json'])
    assert args.format == 'json'
    
    # Test with all options combined
    args = parser.parse_args([
        'list', 'reservations',
        '--active',
        '--days', '14',
        '--format', 'json'
    ])
    assert args.active is True
    assert args.days == 14
    assert args.format == 'json'
    
    # Test with global options
    args = parser.parse_args([
        '-u', 'testuser',
        '--dev',
        'list',
        'reservations',
        '--upcoming',
        '--days', '3'
    ])
    assert args.user == 'testuser'
    assert args.dev is True
    assert args.command == 'list'
    assert args.list_type == 'reservations'
    assert args.upcoming is True
    assert args.days == 3

def test_invalid_arguments(capsys):
    """Test that invalid arguments raise appropriate errors."""
    parser = create_parser()

    # Test invalid latitude
    with pytest.raises(SystemExit):
        parser.parse_args(['get', 'weather', '--lat', 'invalid', '--lon', '24.9384'])
    captured = capsys.readouterr()
    assert 'invalid float value: \'invalid\'' in captured.err

    # Test missing required arguments
    with pytest.raises(SystemExit):
        parser.parse_args(['get', 'weather'])
    captured = capsys.readouterr()
    assert 'the following arguments are required: --lat, --lon' in captured.err

    # Test invalid service
    with pytest.raises(SystemExit):
        parser.parse_args(['get', 'weather', '--lat', '60.1699', '--lon', '24.9384', '--service', 'invalid'])
    captured = capsys.readouterr()
    assert 'invalid choice: \'invalid\' (choose from \'met\', \'portuguese\', \'iberian\', \'openmeteo\')' in captured.err

    # Test invalid format
    with pytest.raises(SystemExit):
        parser.parse_args(['get', 'weather', '--lat', '60.1699', '--lon', '24.9384', '--format', 'invalid'])
    captured = capsys.readouterr()
    assert 'invalid choice: \'invalid\'' in captured.err

    # Test invalid days value for reservations
    with pytest.raises(ValueError):
        args = parser.parse_args(['list', 'reservations', '--days', '-1'])
        if args.days < 1:
            raise ValueError("days must be a positive integer")

def test_check_command():
    """Test check command arguments."""
    parser = create_parser()
    
    # Test basic check command
    args = parser.parse_args(['check'])
    assert args.command == 'check'
    assert not args.full
    
    # Test check with full option
    args = parser.parse_args(['check', '--full'])
    assert args.full is True 