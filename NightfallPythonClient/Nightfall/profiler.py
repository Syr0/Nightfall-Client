#!/usr/bin/env python3
"""
Profiler for Nightfall MUD Client
Tracks function calls, frequency, and CPU usage
"""

import cProfile
import pstats
import io
import sys
import time
from pathlib import Path
from datetime import datetime
import json

class NightfallProfiler:
    def __init__(self, output_dir="profiling_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.profiler = cProfile.Profile()
        self.start_time = None
        self.session_name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def start(self):
        """Start profiling"""
        print(f"[PROFILER] Starting profiling session: {self.session_name}")
        self.start_time = time.time()
        self.profiler.enable()
        
    def stop(self):
        """Stop profiling and save results"""
        self.profiler.disable()
        elapsed = time.time() - self.start_time if self.start_time else 0
        print(f"[PROFILER] Profiling completed. Duration: {elapsed:.2f} seconds")
        
        # Save raw stats
        stats_file = self.output_dir / f"profile_{self.session_name}.stats"
        self.profiler.dump_stats(str(stats_file))
        print(f"[PROFILER] Raw stats saved to: {stats_file}")
        
        # Generate reports
        self._generate_text_report()
        self._generate_json_report()
        self._generate_html_report()
        
    def _generate_text_report(self):
        """Generate human-readable text report"""
        report_file = self.output_dir / f"profile_{self.session_name}.txt"
        
        with open(report_file, 'w') as f:
            # Redirect stdout to file
            old_stdout = sys.stdout
            sys.stdout = f
            
            print(f"Profiling Report - Session: {self.session_name}")
            print("=" * 80)
            
            # Create stats object
            stats = pstats.Stats(self.profiler)
            
            # Sort by cumulative time
            print("\n### TOP 50 FUNCTIONS BY CUMULATIVE TIME ###")
            print("-" * 80)
            stats.sort_stats('cumulative').print_stats(50)
            
            # Sort by total time
            print("\n### TOP 50 FUNCTIONS BY TOTAL TIME ###")
            print("-" * 80)
            stats.sort_stats('time').print_stats(50)
            
            # Sort by call count
            print("\n### TOP 50 MOST CALLED FUNCTIONS ###")
            print("-" * 80)
            stats.sort_stats('calls').print_stats(50)
            
            # Show callers and callees for expensive functions
            print("\n### CALLERS/CALLEES FOR TOP 10 TIME-CONSUMING FUNCTIONS ###")
            print("-" * 80)
            stats.sort_stats('time').print_callers(10)
            print("\n")
            stats.print_callees(10)
            
            sys.stdout = old_stdout
            
        print(f"[PROFILER] Text report saved to: {report_file}")
        
    def _generate_json_report(self):
        """Generate JSON report for further analysis"""
        report_file = self.output_dir / f"profile_{self.session_name}.json"
        
        stats = pstats.Stats(self.profiler)
        stats_dict = {}
        
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            filename, line, func_name = func
            
            # Skip built-in functions for cleaner output
            if not filename.startswith('<'):
                key = f"{filename}:{line}:{func_name}"
                stats_dict[key] = {
                    'filename': filename,
                    'line': line,
                    'function': func_name,
                    'call_count': nc,
                    'recursive_calls': cc - nc,
                    'total_time': tt,
                    'cumulative_time': ct,
                    'avg_time_per_call': tt / nc if nc > 0 else 0,
                    'avg_cumulative_per_call': ct / cc if cc > 0 else 0
                }
        
        # Sort by cumulative time and get top entries
        sorted_stats = sorted(stats_dict.items(), 
                            key=lambda x: x[1]['cumulative_time'], 
                            reverse=True)
        
        report_data = {
            'session': self.session_name,
            'total_functions': len(stats_dict),
            'top_100_by_time': dict(sorted_stats[:100])
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
            
        print(f"[PROFILER] JSON report saved to: {report_file}")
        
    def _generate_html_report(self):
        """Generate interactive HTML report"""
        report_file = self.output_dir / f"profile_{self.session_name}.html"
        
        stats = pstats.Stats(self.profiler)
        stats_list = []
        
        for func, (cc, nc, tt, ct, callers) in stats.stats.items():
            filename, line, func_name = func
            if not filename.startswith('<'):
                # Clean up file paths for readability
                if 'Nightfall' in filename:
                    filename = filename.split('Nightfall')[-1]
                
                stats_list.append({
                    'file': filename,
                    'line': line,
                    'function': func_name,
                    'calls': nc,
                    'total_time': round(tt, 4),
                    'cumulative_time': round(ct, 4),
                    'per_call': round(tt / nc if nc > 0 else 0, 6)
                })
        
        # Sort by cumulative time
        stats_list.sort(key=lambda x: x['cumulative_time'], reverse=True)
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Nightfall Profiling Report - {self.session_name}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 20px;
            background: #1e1e1e;
            color: #e0e0e0;
        }}
        h1 {{
            color: #00ff00;
            border-bottom: 2px solid #00ff00;
            padding-bottom: 10px;
        }}
        .stats {{
            margin: 20px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            background: #2d2d2d;
        }}
        th {{
            background: #00ff00;
            color: #000;
            padding: 10px;
            text-align: left;
            position: sticky;
            top: 0;
            cursor: pointer;
        }}
        th:hover {{
            background: #00dd00;
        }}
        td {{
            padding: 8px;
            border-bottom: 1px solid #444;
        }}
        tr:hover {{
            background: #3d3d3d;
        }}
        .number {{
            text-align: right;
            font-family: 'Consolas', monospace;
        }}
        .function {{
            font-family: 'Consolas', monospace;
            color: #4fc3f7;
        }}
        .file {{
            color: #999;
            font-size: 0.9em;
        }}
        .high-time {{
            color: #ff6b6b;
            font-weight: bold;
        }}
        .medium-time {{
            color: #ffd93d;
        }}
        .search {{
            margin: 20px 0;
            padding: 10px;
            background: #2d2d2d;
            border-radius: 5px;
        }}
        input {{
            background: #1e1e1e;
            color: #e0e0e0;
            border: 1px solid #00ff00;
            padding: 5px 10px;
            width: 300px;
        }}
        .summary {{
            background: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .summary-item {{
            display: inline-block;
            margin: 0 20px;
        }}
    </style>
</head>
<body>
    <h1>Nightfall MUD Client - Profiling Report</h1>
    <div class="summary">
        <span class="summary-item">Session: {self.session_name}</span>
        <span class="summary-item">Total Functions: {len(stats_list)}</span>
        <span class="summary-item">Total Time: {sum(s['total_time'] for s in stats_list):.2f}s</span>
    </div>
    
    <div class="search">
        <label>Search: <input type="text" id="search" placeholder="Filter functions..."></label>
    </div>
    
    <table id="statsTable">
        <thead>
            <tr>
                <th onclick="sortTable(0)">Function</th>
                <th onclick="sortTable(1)">File</th>
                <th onclick="sortTable(2)" class="number">Line</th>
                <th onclick="sortTable(3)" class="number">Calls</th>
                <th onclick="sortTable(4)" class="number">Total Time (s)</th>
                <th onclick="sortTable(5)" class="number">Cumulative (s)</th>
                <th onclick="sortTable(6)" class="number">Per Call (s)</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for stat in stats_list[:500]:  # Top 500 functions
            time_class = ''
            if stat['cumulative_time'] > 1.0:
                time_class = 'high-time'
            elif stat['cumulative_time'] > 0.1:
                time_class = 'medium-time'
                
            html_content += f"""
            <tr>
                <td class="function">{stat['function']}</td>
                <td class="file">{stat['file']}</td>
                <td class="number">{stat['line']}</td>
                <td class="number">{stat['calls']:,}</td>
                <td class="number">{stat['total_time']}</td>
                <td class="number {time_class}">{stat['cumulative_time']}</td>
                <td class="number">{stat['per_call']}</td>
            </tr>
"""
        
        html_content += """
        </tbody>
    </table>
    
    <script>
        // Search functionality
        document.getElementById('search').addEventListener('keyup', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#statsTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
        
        // Sort functionality
        let sortOrder = {};
        
        function sortTable(column) {
            const table = document.getElementById('statsTable');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            sortOrder[column] = !sortOrder[column];
            
            rows.sort((a, b) => {
                let aVal = a.cells[column].textContent;
                let bVal = b.cells[column].textContent;
                
                // Handle numeric columns
                if (column >= 2) {
                    aVal = parseFloat(aVal.replace(/,/g, '')) || 0;
                    bVal = parseFloat(bVal.replace(/,/g, '')) || 0;
                }
                
                if (sortOrder[column]) {
                    return aVal > bVal ? 1 : -1;
                } else {
                    return aVal < bVal ? 1 : -1;
                }
            });
            
            rows.forEach(row => tbody.appendChild(row));
        }
    </script>
</body>
</html>
"""
        
        with open(report_file, 'w') as f:
            f.write(html_content)
            
        print(f"[PROFILER] HTML report saved to: {report_file}")
        print(f"[PROFILER] Open in browser: file:///{report_file.absolute()}")


def run_with_profiling():
    """Run the main application with profiling enabled"""
    profiler = NightfallProfiler()
    
    try:
        # Import main after profiler is ready
        from main import main
        
        # Start profiling
        profiler.start()
        
        # Run the application
        main()
        
    except KeyboardInterrupt:
        print("\n[PROFILER] Application interrupted by user")
    except Exception as e:
        print(f"[PROFILER] Application error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop profiling and generate reports
        profiler.stop()


if __name__ == "__main__":
    print("=" * 80)
    print("NIGHTFALL MUD CLIENT - PROFILING MODE")
    print("=" * 80)
    print("This will run the application with profiling enabled.")
    print("Performance data will be collected and saved to ./profiling_results/")
    print("Press Ctrl+C to stop the application and generate reports.")
    print("=" * 80)
    
    run_with_profiling()