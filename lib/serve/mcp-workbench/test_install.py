#!/usr/bin/env python3
"""
Simple test to verify MCP Workbench installation.
Run this after installing to verify everything works.
"""

def test_imports():
    """Test that all main modules can be imported."""
    try:
        # Test core imports
        from mcpworkbench.core.base_tool import BaseTool
        from mcpworkbench.core.annotations import mcp_tool
        from mcpworkbench.core.tool_discovery import ToolDiscovery
        from mcpworkbench.core.tool_registry import ToolRegistry
        
        # Test adapter imports
        from mcpworkbench.adapters.tool_adapter import create_adapter
        
        # Test config imports
        from mcpworkbench.config.models import ServerConfig
        
        # Test server imports
        from mcpworkbench.server.mcp_server import MCPWorkbenchServer
        
        print("✅ All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_cli_available():
    """Test that the CLI command is available."""
    import subprocess
    import sys
    
    try:
        result = subprocess.run([sys.executable, "-m", "mcpworkbench.cli", "--help"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "mcpworkbench" in result.stdout.lower():
            print("✅ CLI command is available!")
            return True
        else:
            print(f"❌ CLI test failed. Return code: {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
        return False


def test_basic_functionality():
    """Test basic functionality works."""
    try:
        # Create a simple tool class
        from mcpworkbench.core.base_tool import BaseTool
        
        class TestTool(BaseTool):
            def __init__(self):
                super().__init__("test", "A test tool")
            
            async def execute(self, **kwargs):
                return {"result": "test successful"}
        
        # Test tool instantiation
        tool = TestTool()
        assert tool.name == "test"
        assert tool.description == "A test tool"
        
        # Test annotation
        from mcpworkbench.core.annotations import mcp_tool
        
        @mcp_tool(name="test_func", description="Test function")
        def test_func():
            return "annotated test successful"
        
        assert hasattr(test_func, '_is_mcp_tool')
        
        print("✅ Basic functionality test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def main():
    """Run all installation tests."""
    print("Testing MCP Workbench installation...")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("CLI Test", test_cli_available), 
        ("Basic Functionality Test", test_basic_functionality)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} failed")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 Installation verification successful!")
        print("\nYou can now use MCP Workbench:")
        print("  mcpworkbench --help")
        print("  python -m mcpworkbench.cli --help")
    else:
        print("❌ Installation verification failed!")
        print("\nTry reinstalling:")
        print("  pip install -e .")
        print("  # or")
        print("  pip install -e \".[dev]\"")
    
    return passed == total


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
