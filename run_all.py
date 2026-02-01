"""
Main entry point that runs all automation projects concurrently.
Each project runs in its own asyncio task.
"""

import asyncio
import sys
import os
import importlib.util

# Add project paths to sys.path
PROJECTS = [
    {
        "name": "video_creator",
        "path": "projects/video_creator/src",
        "main_module": "main",
        "main_function": "main"
    },
    {
        "name": "instagram_stories",
        "path": "projects/instagram_stories/src",
        "main_module": "main",
        "main_function": "main"
    }
]


def load_project_main(project: dict):
    """Dynamically load a project's main module."""
    project_path = os.path.join(os.path.dirname(__file__), project["path"])
    
    # Check if project exists
    main_file = os.path.join(project_path, f"{project['main_module']}.py")
    if not os.path.exists(main_file):
        print(f"⚠️  Project '{project['name']}' not found or not initialized (missing {main_file})")
        return None
    
    # Add project path to sys.path for imports
    if project_path not in sys.path:
        sys.path.insert(0, project_path)
    
    # Load the module
    spec = importlib.util.spec_from_file_location(
        f"{project['name']}.{project['main_module']}", 
        main_file
    )
    module = importlib.util.module_from_spec(spec)
    
    # Set the module's __name__ properly
    sys.modules[f"{project['name']}_{project['main_module']}"] = module
    
    try:
        spec.loader.exec_module(module)
        return getattr(module, project["main_function"], None)
    except Exception as e:
        print(f"❌ Failed to load project '{project['name']}': {e}")
        return None


async def run_project(project: dict):
    """Run a single project's main function."""
    print(f"🚀 Starting project: {project['name']}")
    
    main_func = load_project_main(project)
    if main_func is None:
        print(f"⏭️  Skipping project '{project['name']}' (not available)")
        return
    
    try:
        if asyncio.iscoroutinefunction(main_func):
            await main_func()
        else:
            await asyncio.to_thread(main_func)
    except Exception as e:
        print(f"❌ Project '{project['name']}' crashed: {e}")


async def main():
    """Main entry point - runs all projects concurrently."""
    print("=" * 60)
    print("🤖 Parties247 Automation Suite")
    print("=" * 60)
    print(f"📦 Registered projects: {[p['name'] for p in PROJECTS]}")
    print("=" * 60)
    
    # Create tasks for all projects
    tasks = [asyncio.create_task(run_project(project)) for project in PROJECTS]
    
    # Wait for all projects (they should run indefinitely)
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Shutting down all projects...")
        for task in tasks:
            task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
