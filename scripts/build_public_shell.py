import os
import shutil
import ast
# import astor  # Removed dependency
import sys
from pathlib import Path

# Configuration
SOURCE_DIR = Path("/root/PolymarketWhales")
DEST_DIR = SOURCE_DIR / "public_export"

# Files/Dirs to Ignore completely
IGNORE_PATTERNS = [
    ".git",
    "__pycache__",
    "venv",
    ".env",
    ".env.*", # sensitive envs
    "data/trades.db",
    "data/*.db", # Exclude all sqlite dbs
    "*.db",
    "bot.log",
    "bot_output.log",
    "scripts/build_public_shell.py", # Don't export the build script itself
    "storage", # Usually contains sessions
]

# Files to Keep As-Is (No Stubbing)
KEEP_AS_IS = [
    "requirements.txt",
    "run.sh",
    "core/localization.py", 
    ".gitignore",
    "twitter_settings.json", # Maybe structure is fine?
    "user_settings.json"
]

# Files to Stub (Python files not in KEEP_AS_IS)
# We will stub all other .py files.

def should_ignore(path):
    for pattern in IGNORE_PATTERNS:
        if path.match(pattern) or pattern in str(path):
            return True
    return False

class CodeStubber(ast.NodeTransformer):
    """
    Replaces function bodies with 'pass' or placeholders,
    keeping docstrings.
    """
    def visit_FunctionDef(self, node):
        new_body = []
        
        # Check for docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, (ast.Str, ast.Constant))):
            new_body.append(node.body[0]) # Keep docstring
        
        # Add placeholder
        # We just use pass to avoid 'logging' NameError if not imported
        new_body.append(ast.Pass())
        
        node.body = new_body
        return node

    def visit_AsyncFunctionDef(self, node):
        return self.visit_FunctionDef(node)

def stub_python_file(src_path, dest_path):
    print(f"Stubbing: {src_path} -> {dest_path}")
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            source = f.read()
        
        tree = ast.parse(source)
        stubber = CodeStubber()
        new_tree = stubber.visit(tree)
        ast.fix_missing_locations(new_tree)
        
        # Unparse
        new_source = ast.unparse(new_tree)
            
        with open(dest_path, "w", encoding="utf-8") as f:
            f.write("# PUBLIC SHELL VERSION\n")
            f.write(new_source)
            
    except Exception as e:
        print(f"Failed to stub {src_path}: {e}")
        # Fallback to empty file or copy
        shutil.copy2(src_path, dest_path)

def main():
    if not DEST_DIR.exists():
        DEST_DIR.mkdir()
    else:
        # Clear directory but keep .git
        print(f"Cleaning {DEST_DIR} (preserving .git)...")
        for item in DEST_DIR.iterdir():
            if item.name == ".git":
                continue
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    print(f"Building Public Shell from {SOURCE_DIR} to {DEST_DIR}...")

    for root, dirs, files in os.walk(SOURCE_DIR):
        # Filter directories
        dirs[:] = [d for d in dirs if not should_ignore(Path(root) / d)]
        
        rel_root = Path(root).relative_to(SOURCE_DIR)
        dest_root = DEST_DIR / rel_root
        dest_root.mkdir(exist_ok=True)

        for file in files:
            src_file = Path(root) / file
            dest_file = dest_root / file
            rel_file_path = rel_root / file

            if should_ignore(rel_file_path):
                continue
            
            # Special Handling
            if file == "README.md":
                # Create a modified README
                with open(src_file, "r") as f:
                    content = f.read()
                with open(dest_file, "w") as f:
                    f.write("# PUBLIC SHELL REPOSITORY\n")
                    f.write("> This is a public demonstration shell. Core logic is stripped.\n\n")
                    f.write(content)
                continue

            if file == ".env.example":
                shutil.copy2(src_file, dest_file)
                continue

            # Python files logic
            if file.endswith(".py"):
                if str(rel_file_path) in KEEP_AS_IS:
                    shutil.copy2(src_file, dest_file)
                else:
                    stub_python_file(src_file, dest_file)
            else:
                # Copy other files as is (json, sh, txt)
                shutil.copy2(src_file, dest_file)

    print("Done! Public shell created.")

if __name__ == "__main__":
    main()
