#!/bin/bash

echo "========================================"
echo "Nightfall MUD Client - Profiling Mode"
echo "========================================"
echo ""
echo "Starting profiled run..."
echo "Close the application when done to generate reports."
echo ""

python3 main_with_options.py --profile

echo ""
echo "========================================"
echo "Profiling complete!"
echo "Reports saved in: profiling_results/"
echo ""
echo "To analyze the results, run:"
echo "  python3 analyze_profile.py profiling_results/[latest].stats"
echo ""
echo "To view HTML report, open:"
echo "  profiling_results/profile_[timestamp].html"
echo "========================================"