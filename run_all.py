"""
Main entry point that runs all automation projects concurrently.
Each project runs in its own asyncio task.
"""

import asyncio
import sys
import os

# Add project paths to sys.path
PROJECTS = [
    {
        "name": "parties247_bot",
        "path": "projects/video_creator/src",
        "main_module": "main",
        "main_function": "main"
    },
    {
        "name": "content_discovery",
        "path": "projects/content_discovery/src",
        "main_module": "main",
        "main_function": "main"
    },
    {
        "name": "tiktok_trend_hunter",
        "path": "projects/tiktok_trend_hunter",
        "main_module": "trend_hunter",
        "main_function": "run_scheduler"
    }
]



async def run_project_process(project: dict):
    """Run a project in a separate process."""
    print(f"🚀 Starting project: {project['name']}")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_cwd = os.path.join(base_dir, project["path"])
    main_file = f"{project['main_module']}.py"
    
    # Check if file exists
    if not os.path.exists(os.path.join(project_cwd, main_file)):
        print(f"⚠️  Project '{project['name']}' missing {main_file} in {project_cwd}")
        return

    while True:
        try:
            # Run as separate process with its own working directory
            # This ensures imports like 'from services...' resolve to the correct project
            process = await asyncio.create_subprocess_exec(
                sys.executable, 
                main_file,
                cwd=project_cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            print(f"✅ Project '{project['name']}' started (PID: {process.pid})")
            
            # Helper to print output
            async def log_stream(stream, prefix):
                while True:
                    line = await stream.readline()
                    if not line: break
                    try:
                        decoded = line.decode().strip()
                        if decoded: print(f"[{prefix}] {decoded}")
                    except: pass

            # Monitor outputs
            await asyncio.gather(
                log_stream(process.stdout, project['name']),
                log_stream(process.stderr, f"{project['name']} ERROR")
            )
            
            await process.wait()
            
            print(f"❌ Project '{project['name']}' exited with code {process.returncode}. Restarting in 5s...")
            await asyncio.sleep(5)
            
        except asyncio.CancelledError:
            print(f"🛑 Stopping project '{project['name']}'...")
            if process:
                process.terminate()
                try:
                    await process.wait()
                except:
                    pass
            break
        except Exception as e:
            print(f"🔥 Error launching '{project['name']}': {e}")
            await asyncio.sleep(5)


async def main():
    """Main entry point - runs all projects concurrently."""
    print("=" * 60)
    print("🤖 Parties247 Automation Suite")
    print("=" * 60)
    print(f"📦 Registered projects: {[p['name'] for p in PROJECTS]}")
    print("=" * 60)
    
    # Create tasks for all projects
    tasks = [asyncio.create_task(run_project_process(project)) for project in PROJECTS]
    
    # Wait for all projects
    try:
        await asyncio.gather(*tasks)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Shutting down suite...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    # Windows-specific event loop policy for subprocesses
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
