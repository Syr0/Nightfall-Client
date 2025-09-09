#!/usr/bin/env python3
"""
Profile Analysis Tool for Nightfall MUD Client
Analyzes and visualizes profiling data
"""

import pstats
import sys
import os
from pathlib import Path
import argparse
from datetime import datetime

class ProfileAnalyzer:
    def __init__(self, stats_file):
        self.stats_file = Path(stats_file)
        if not self.stats_file.exists():
            raise FileNotFoundError(f"Stats file not found: {stats_file}")
        
        self.stats = pstats.Stats(str(self.stats_file))
        
    def print_summary(self):
        """Print a comprehensive summary of the profiling data"""
        print("=" * 80)
        print(f"PROFILE ANALYSIS: {self.stats_file.name}")
        print("=" * 80)
        
        # Get total runtime
        total_time = sum(data[2] for data in self.stats.stats.values())
        total_calls = sum(data[0] for data in self.stats.stats.values())
        
        print(f"\nTotal execution time: {total_time:.3f} seconds")
        print(f"Total function calls: {total_calls:,}")
        print(f"Unique functions: {len(self.stats.stats)}")
        
    def analyze_by_module(self):
        """Group statistics by module"""
        print("\n" + "=" * 80)
        print("ANALYSIS BY MODULE")
        print("=" * 80)
        
        modules = {}
        for func, (cc, nc, tt, ct, callers) in self.stats.stats.items():
            filename = func[0]
            
            # Extract module name
            if 'Nightfall' in filename:
                parts = filename.split('Nightfall')[-1].split('\\')
                if len(parts) > 1:
                    module = parts[1] if parts[1] != '' else 'root'
                else:
                    module = 'root'
            else:
                module = 'external'
            
            if module not in modules:
                modules[module] = {
                    'functions': 0,
                    'calls': 0,
                    'time': 0,
                    'cumulative': 0
                }
            
            modules[module]['functions'] += 1
            modules[module]['calls'] += nc
            modules[module]['time'] += tt
            modules[module]['cumulative'] += ct
        
        # Sort by cumulative time
        sorted_modules = sorted(modules.items(), 
                               key=lambda x: x[1]['cumulative'], 
                               reverse=True)
        
        print(f"{'Module':<20} {'Functions':<12} {'Calls':<15} {'Time (s)':<12} {'Cumulative (s)':<15}")
        print("-" * 80)
        
        for module, data in sorted_modules:
            print(f"{module:<20} {data['functions']:<12} {data['calls']:<15,} "
                  f"{data['time']:<12.3f} {data['cumulative']:<15.3f}")
    
    def find_hotspots(self, top_n=20):
        """Find performance hotspots"""
        print("\n" + "=" * 80)
        print(f"TOP {top_n} PERFORMANCE HOTSPOTS")
        print("=" * 80)
        
        # Sort by cumulative time
        sorted_stats = sorted(self.stats.stats.items(),
                            key=lambda x: x[1][3],  # cumulative time
                            reverse=True)
        
        print(f"\n{'Function':<50} {'Calls':<10} {'Total(s)':<10} {'Cumul(s)':<10} {'Per Call':<10}")
        print("-" * 90)
        
        for i, (func, (cc, nc, tt, ct, callers)) in enumerate(sorted_stats[:top_n]):
            filename, line, func_name = func
            
            # Simplify filename
            if 'Nightfall' in filename:
                filename = '...' + filename.split('Nightfall')[-1]
            
            location = f"{func_name} ({filename}:{line})"
            if len(location) > 50:
                location = location[:47] + "..."
                
            per_call = tt / nc if nc > 0 else 0
            
            print(f"{location:<50} {nc:<10,} {tt:<10.3f} {ct:<10.3f} {per_call:<10.6f}")
    
    def find_most_called(self, top_n=20):
        """Find most frequently called functions"""
        print("\n" + "=" * 80)
        print(f"TOP {top_n} MOST CALLED FUNCTIONS")
        print("=" * 80)
        
        # Sort by call count
        sorted_stats = sorted(self.stats.stats.items(),
                            key=lambda x: x[1][1],  # call count
                            reverse=True)
        
        print(f"\n{'Function':<50} {'Calls':<15} {'Total Time (s)':<15}")
        print("-" * 80)
        
        for i, (func, (cc, nc, tt, ct, callers)) in enumerate(sorted_stats[:top_n]):
            filename, line, func_name = func
            
            # Simplify filename
            if 'Nightfall' in filename:
                filename = '...' + filename.split('Nightfall')[-1]
            
            location = f"{func_name} ({filename}:{line})"
            if len(location) > 50:
                location = location[:47] + "..."
            
            print(f"{location:<50} {nc:<15,} {tt:<15.3f}")
    
    def analyze_call_chains(self, function_pattern=None):
        """Analyze call chains for specific functions"""
        print("\n" + "=" * 80)
        print("CALL CHAIN ANALYSIS")
        print("=" * 80)
        
        if function_pattern:
            print(f"Filtering for: {function_pattern}")
        
        # Find functions matching pattern
        matching_funcs = []
        for func in self.stats.stats.keys():
            func_name = func[2]
            if not function_pattern or function_pattern.lower() in func_name.lower():
                matching_funcs.append(func)
        
        if not matching_funcs:
            print("No matching functions found")
            return
        
        # Show top 5 matching functions with their callers
        for func in matching_funcs[:5]:
            filename, line, func_name = func
            stats = self.stats.stats[func]
            
            print(f"\n{func_name} ({filename}:{line})")
            print(f"  Calls: {stats[1]:,}, Time: {stats[2]:.3f}s")
            
            # Show callers
            callers = stats[4]
            if callers:
                print("  Called by:")
                sorted_callers = sorted(callers.items(), 
                                      key=lambda x: x[1][3],  # sort by cumulative time
                                      reverse=True)
                for caller_func, caller_stats in sorted_callers[:5]:
                    caller_name = f"{caller_func[2]} ({caller_func[0]}:{caller_func[1]})"
                    print(f"    - {caller_name}")
                    print(f"      Calls: {caller_stats[0]}, Time: {caller_stats[3]:.3f}s")
    
    def export_csv(self, output_file=None):
        """Export profiling data to CSV for Excel analysis"""
        if not output_file:
            output_file = self.stats_file.with_suffix('.csv')
        
        print(f"\nExporting to CSV: {output_file}")
        
        with open(output_file, 'w') as f:
            # Write header
            f.write("Module,File,Line,Function,Calls,Total_Time,Cumulative_Time,Per_Call\n")
            
            # Write data
            for func, (cc, nc, tt, ct, callers) in self.stats.stats.items():
                filename, line, func_name = func
                
                # Extract module
                if 'Nightfall' in filename:
                    parts = filename.split('Nightfall')[-1].split('\\')
                    module = parts[1] if len(parts) > 1 and parts[1] != '' else 'root'
                else:
                    module = 'external'
                
                per_call = tt / nc if nc > 0 else 0
                
                # Escape commas in filenames
                filename = filename.replace(',', ';')
                func_name = func_name.replace(',', ';')
                
                f.write(f"{module},{filename},{line},{func_name},{nc},{tt:.6f},{ct:.6f},{per_call:.9f}\n")
        
        print(f"CSV export complete: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Analyze Nightfall profiling data')
    parser.add_argument('stats_file', help='Path to .stats file')
    parser.add_argument('--top', type=int, default=20, 
                       help='Number of top functions to show (default: 20)')
    parser.add_argument('--function', help='Analyze specific function call chains')
    parser.add_argument('--csv', action='store_true', 
                       help='Export data to CSV')
    parser.add_argument('--all', action='store_true',
                       help='Run all analyses')
    
    args = parser.parse_args()
    
    try:
        analyzer = ProfileAnalyzer(args.stats_file)
        
        # Always show summary
        analyzer.print_summary()
        
        if args.all:
            analyzer.analyze_by_module()
            analyzer.find_hotspots(args.top)
            analyzer.find_most_called(args.top)
            if args.csv:
                analyzer.export_csv()
        else:
            # Show default analyses
            analyzer.analyze_by_module()
            analyzer.find_hotspots(args.top)
            
            if args.function:
                analyzer.analyze_call_chains(args.function)
            
            if args.csv:
                analyzer.export_csv()
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nAvailable stats files in profiling_results/:")
        if Path('profiling_results').exists():
            for f in Path('profiling_results').glob('*.stats'):
                print(f"  - {f}")
    except Exception as e:
        print(f"Error analyzing profile: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()