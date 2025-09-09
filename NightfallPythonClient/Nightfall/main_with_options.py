# main_with_options.py
import os
import sys
import argparse

# Change to script directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Main application entry point"""
    # Import and run install check
    from install import main as install_dependencies
    install_dependencies()
    
    from gui.mainwindow import MainWindow
    import tkinter as tk
    
    root = tk.Tk()
    app = MainWindow(root)
    
    def on_closing():
        # Save camera state before closing
        if hasattr(app, 'map_viewer') and app.map_viewer.displayed_zone_id:
            zone_key = f"{app.map_viewer.displayed_zone_id}_{app.map_viewer.current_level}"
            app.map_viewer.camera.save_zone_state(zone_key)
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Nightfall MUD Client')
    parser.add_argument('--profile', action='store_true', 
                       help='Run with profiling enabled')
    parser.add_argument('--profile-dir', default='profiling_results',
                       help='Directory for profiling output (default: profiling_results)')
    
    args = parser.parse_args()
    
    if args.profile:
        print("=" * 80)
        print("NIGHTFALL MUD CLIENT - PROFILING MODE")
        print("=" * 80)
        print(f"Performance data will be saved to: {args.profile_dir}/")
        print("Close the application normally to generate profiling reports.")
        print("=" * 80)
        
        from profiler import NightfallProfiler
        
        profiler = NightfallProfiler(output_dir=args.profile_dir)
        
        try:
            profiler.start()
            main()
        except KeyboardInterrupt:
            print("\n[PROFILER] Application interrupted by user")
        except Exception as e:
            print(f"[PROFILER] Application error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            profiler.stop()
    else:
        # Normal execution
        main()