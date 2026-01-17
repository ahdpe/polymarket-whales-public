import os
import shutil
import ast
import json
import re
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
    "send_broadcast.py",  # Admin-only broadcast script
    "storage", # Usually contains sessions
    "public_export", # Don't copy the public export into itself
    "services/status_service.py",
    "services/status_server.py",
]

# Files to Keep As-Is (No Stubbing)
KEEP_AS_IS = [
    "requirements.txt",
    "run.sh",
    "core/localization.py", 
    ".gitignore",
    "twitter_settings.json",
    # user_settings.json is handled separately (template only)
]

# Sections to remove from README (patterns)
SECTIONS_TO_REMOVE = [
    r"#{1,4}\s*\d*\.?\s*Twitter\s*(Интеграция|Integration)",
    r"#{1,4}\s*\d*\.?\s*(Администрирование|Administration)",
    r"#{1,4}\s*\d*\.?\s*(Статус-дашборд|Status Dashboard)",
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

def sanitize_readme(content):
    """
    Remove admin-only sections from README:
    - Twitter Integration / Twitter Интеграция
    - Administration / Администрирование
    Also renumbers remaining sections.
    """
    lines = content.split('\n')
    result = []
    skip_section = False
    current_section_level = None
    
    for line in lines:
        # Check if this line starts a section to remove
        should_skip = False
        for pattern in SECTIONS_TO_REMOVE:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                should_skip = True
                # Count the # symbols to know the section level
                match = re.match(r'^(#{1,4})', line.strip())
                if match:
                    current_section_level = len(match.group(1))
                skip_section = True
                break
        
        if should_skip:
            continue
            
        # If we're skipping and hit a new section of same or higher level, stop skipping
        if skip_section:
            match = re.match(r'^(#{1,4})\s', line.strip())
            if match:
                level = len(match.group(1))
                if level <= current_section_level:
                    skip_section = False
                    current_section_level = None
        
        if not skip_section:
            result.append(line)
    
    # Renumber sections (#### N. -> sequential numbering)
    final_result = []
    section_counters = {}  # Track counters per section level
    
    for line in result:
        # Match numbered sections like "#### 5. Something" or "#### 6. Something"
        match = re.match(r'^(#{1,4})\s+(\d+)\.\s+(.+)$', line)
        if match:
            hashes = match.group(1)
            title = match.group(3)
            level = len(hashes)
            
            # Initialize or increment counter for this level
            if level not in section_counters:
                section_counters[level] = 0
            section_counters[level] += 1
            
            # Reset deeper level counters
            for l in list(section_counters.keys()):
                if l > level:
                    del section_counters[l]
            
            new_line = f"{hashes} {section_counters[level]}. {title}"
            final_result.append(new_line)
        else:
            final_result.append(line)
    
    return '\n'.join(final_result)

def create_template_user_settings():
    """Create a template user_settings.json with example structure only."""
    template = {
        "filters": {"example_user_id": 50000},
        "categories": {
            "example_user_id": {
                "all": True,
                "other": True,
                "crypto": True,
                "sports": True
            }
        },
        "languages": {"example_user_id": "en"},
        "statuses": {"example_user_id": True},
        "usernames": {"example_user_id": "example_username"},
        "probabilities": {"example_user_id": "1_99"},
        "side_types": {
            "example_user_id": {
                "all": False,
                "BUY": True,
                "SELL": True,
                "SPLIT": False,
                "MERGE": False,
                "REDEEM": False
            }
        },
        "wallet_ages": {
            "example_user_id": {"min_days": None, "max_days": None}
        },
        "open_positions": {
            "example_user_id": {"min_count": None, "max_count": None}
        },
        "bot_enabled": True
    }
    return json.dumps(template, indent=2)

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
                # Create a sanitized README (remove admin/Twitter sections)
                print(f"Sanitizing README: {src_file}")
                with open(src_file, "r", encoding="utf-8") as f:
                    content = f.read()
                sanitized = sanitize_readme(content)
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write("# PUBLIC SHELL REPOSITORY\n")
                    f.write("> This is a public demonstration shell. Core logic is stripped.\n\n")
                    f.write(sanitized)
                continue
            
            if file == "user_settings.json":
                # Create template user_settings.json (no real user data)
                print(f"Creating template user_settings.json")
                with open(dest_file, "w", encoding="utf-8") as f:
                    f.write(create_template_user_settings())
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
