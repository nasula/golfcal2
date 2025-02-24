#!/usr/bin/env python3
"""Test runner for golfcal2."""

import os
import sys
import unittest

import coverage


def run_tests():
    """Run all tests with coverage reporting."""
    # Start coverage measurement
    cov = coverage.Coverage(
        branch=True,
        source=['golfcal2'],
        omit=[
            '*/tests/*',
            '*/migrations/*',
            '*/site-packages/*',
            '*/__pycache__/*'
        ]
    )
    cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Stop coverage measurement and report
    cov.stop()
    cov.save()
    
    print('\nCoverage Summary:')
    cov.report()
    
    # Generate HTML coverage report
    cov.html_report(directory='coverage_html')
    print('\nDetailed coverage report generated in coverage_html/index.html')
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1) 