#!/usr/bin/env python3
"""
Code Analyzer Script

This script analyzes the code in a repository:
- Scans all files in the repository
- Identifies functions, classes, and methods
- Generates structured JSON output for further processing
- Works in GitHub Actions
"""

import os
import sys
import json
import hashlib
import datetime
import fnmatch
import logging
import itertools
from typing import Dict, List, Optional, Set, Any
from pathlib import Path
import importlib

try:
    from tree_sitter import Language, Parser
except ImportError:
    print(
        "Error: tree-sitter package not found. Install with 'pip install tree-sitter'"
    )
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("code-analyzer")

# Configure paths
REPO_PATH = os.environ.get("GITHUB_WORKSPACE", os.getcwd())
DOCAI_DIR = os.path.join(REPO_PATH, ".docai")
ELEMENTS_DB_PATH = os.path.join(DOCAI_DIR, "code_elements.json")

# Ensure .docai directory exists
os.makedirs(DOCAI_DIR, exist_ok=True)

# Language extensions mapping
LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "tsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "c_sharp",
    ".cpp": "cpp",
    ".c": "c",
}

# Load language libraries
try:
    # Tree-sitter language modules
    import tree_sitter_python
    import tree_sitter_javascript
    import tree_sitter_typescript

    try:
        import tree_sitter_java
        import tree_sitter_go
        import tree_sitter_rust
        import tree_sitter_ruby
        import tree_sitter_php
        import tree_sitter_c_sharp
        import tree_sitter_cpp
    except ImportError:
        logger.warning("Some optional language modules could not be imported")

    # Map language names to their tree-sitter language modules
    LANGUAGE_MODULES = {
        "python": tree_sitter_python.language,
        "javascript": tree_sitter_javascript.language,
        "typescript": tree_sitter_typescript.language_typescript,
        "tsx": tree_sitter_typescript.language_tsx,
    }

    # Add optional languages if available
    try:
        LANGUAGE_MODULES["java"] = tree_sitter_java.language
        LANGUAGE_MODULES["go"] = tree_sitter_go.language
        LANGUAGE_MODULES["rust"] = tree_sitter_rust.language
        LANGUAGE_MODULES["ruby"] = tree_sitter_ruby.language
        LANGUAGE_MODULES["php"] = tree_sitter_php.language
        LANGUAGE_MODULES["c_sharp"] = tree_sitter_c_sharp.language
        LANGUAGE_MODULES["cpp"] = tree_sitter_cpp.language
        LANGUAGE_MODULES["c"] = tree_sitter_cpp.language  # Use C++ parser for C
    except NameError:
        pass  # Skip if language module wasn't imported

except ImportError:
    logger.error("Core tree-sitter language modules could not be imported")
    sys.exit(1)


class CodeAnalyzer:
    """Analyzes code in a repository using tree-sitter."""

    def __init__(self, repo_path: str):
        """
        Initialize the CodeAnalyzer.

        Args:
            repo_path: Path to the repository
        """
        self.repo_path = repo_path
        self.languages = self._setup_tree_sitter()
        self.parser = Parser()
        self.excluded_paths = self._load_excluded_paths()
        self.current_file = ""
        logger.info(f"Initialized analyzer for repository at {repo_path}")
        logger.info(f"Loaded {len(self.languages)} language parsers")

    def _setup_tree_sitter(self) -> Dict[str, Language]:
        """Initialize and load tree-sitter languages."""
        import pkg_resources
        lang_objects = {}
        language_map = {
            "python": "tree_sitter_python",
            "javascript": "tree_sitter_javascript",
            "typescript": "tree_sitter_typescript",
            "tsx": "tree_sitter_tsx",
            "java": "tree_sitter_java",
            "go": "tree_sitter_go",
            "rust": "tree_sitter_rust",
            "ruby": "tree_sitter_ruby",
            "php": "tree_sitter_php",
            "c_sharp": "tree_sitter_c_sharp",
            "cpp": "tree_sitter_cpp",
            "c": "tree_sitter_cpp",
        }

        for lang_name, module_name in language_map.items():
            try:
                module = importlib.import_module(module_name)
                language_path = pkg_resources.resource_filename(module_name, f"vendor/tree-sitter-{lang_name}/src")
                lang_objects[lang_name] = Language(language_path, lang_name)
                logger.info(f"Loaded {lang_name} parser")
            except Exception as e:
                logger.warning(f"Failed to load {lang_name} parser: {e}")

        return lang_objects

    def _load_excluded_paths(self) -> List[str]:
        """Load paths that should be excluded from analysis."""
        config_path = os.path.join(DOCAI_DIR, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                excluded_paths = config.get("excluded_paths", [])
                logger.info(f"Loaded {len(excluded_paths)} excluded paths from config")
                return excluded_paths
            except Exception as e:
                logger.error(f"Error loading config: {e}")

        # Default exclusions if no config
        return [
            ".git/*",
            ".github/*",
            "node_modules/*",
            "venv/*",
            ".env/*",
            "env/*",
            ".venv/*",
            "build/*",
            "dist/*",
            "__pycache__/*",
            "*.pyc",
            "*.min.js",
            "*.bundle.js",
            "*.log",
            "docs/*",
            "*.md",
            ".docai/*",
            "babel.config.js",
            # Add more standard exclusions here
        ]

    def _should_exclude_path(self, file_path: str) -> bool:
        """Check if a file path should be excluded based on config patterns."""
        try:
            # Get relative path for matching
            rel_path = os.path.relpath(file_path, self.repo_path)

            # Check each pattern
            for pattern in self.excluded_paths:
                if fnmatch.fnmatch(rel_path, pattern):
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking exclusion for {file_path}: {e}")
            return False

    def _get_file_language(self, file_path: str) -> Optional[str]:
        """
        Determine the programming language of a file based on its extension.

        Args:
            file_path: Path to the file

        Returns:
            Language name or None if not supported
        """
        extension = os.path.splitext(file_path)[1].lower()
        if extension == ".js":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "React" in content or "<" in content:
                        return "tsx"
            except:
                pass
        return LANGUAGE_EXTENSIONS.get(extension)

    def _iter_tree(self, node):
        """Helper method to iterate through all nodes in a tree."""
        yield node
        for child in node.children:
            yield from self._iter_tree(child)

    def _format_code(self, code: str) -> str:
        """Format code to remove unwanted whitespace and normalize line endings."""
        if not code:
            return code

        # Split into lines and remove empty lines at start/end
        lines = code.strip().split("\n")

        # Find common indentation
        def get_indent(line):
            return len(line) - len(line.lstrip())

        indents = [get_indent(line) for line in lines if line.strip()]
        if indents:
            min_indent = min(indents)
            # Remove common indentation but preserve relative indentation
            lines = [line[min_indent:] if line.strip() else "" for line in lines]

        # Join lines with normalized line endings
        formatted = "\n".join(lines)

        # Remove multiple blank lines
        formatted = "\n".join(
            line for line, _ in itertools.groupby(formatted.splitlines())
        )

        return formatted

    def _generate_element_id(self, element: Dict) -> str:
        """
        Generate a unique ID for a code element.

        Args:
            element: Code element dictionary

        Returns:
            Unique ID string
        """
        rel_path = os.path.relpath(element["file_path"], self.repo_path)
        unique_str = f"{rel_path}:{element['name']}:{element['type']}"
        return hashlib.md5(unique_str.encode()).hexdigest()

    def _get_element_info(self, node, content: bytes, lang_name: str) -> Optional[Dict]:
        try:
            # Python-specific handling
            if lang_name == "python":
                if node.type == "function_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        return {
                            "type": "function",
                            "name": name_node.text.decode("utf-8"),
                        }
    
                elif node.type == "class_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        return {"type": "class", "name": name_node.text.decode("utf-8")}
    
                elif node.type == "method_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_node = self._find_parent_class(node)
                        if class_node:
                            class_name = class_node.child_by_field_name("name").text.decode("utf-8")
                            method_name = name_node.text.decode("utf-8")
                            return {
                                "type": "method",
                                "name": f"{class_name}.{method_name}",
                            }
                        else:
                            return {
                                "type": "function",
                                "name": name_node.text.decode("utf-8"),
                            }
    
                elif node.type == "assignment" and self._is_module_level(node):
                    target = node.child_by_field_name("left")
                    if target and target.type in ["identifier", "attribute"]:
                        var_name = target.text.decode("utf-8")
                        return {
                            "type": "variable_definition",
                            "name": var_name,
                        }
    
                elif node.type in ["import_statement", "import_from_statement"] and self._is_module_level(node):
                    import_text = content[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
                    import_hash = hashlib.md5(import_text.encode()).hexdigest()[:8]
                    return {
                        "type": "import_statement",
                        "name": f"import_{import_hash}",
                        "import_text": import_text,
                    }
    
            # JavaScript/TypeScript handling
            elif lang_name in ["javascript", "typescript", "tsx", "jsx"]:
                if node.type == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        body = node.child_by_field_name("body")
                        has_jsx = any(
                            child.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]
                            for child in self._iter_tree(body or node)
                        )
                        logger.debug(f"Detected function {name_node.text.decode('utf-8')}, has_jsx: {has_jsx}")
                        return {
                            "type": "component" if has_jsx else "function",
                            "name": name_node.text.decode("utf-8"),
                        }
    
                elif node.type == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        return {"type": "class", "name": name_node.text.decode("utf-8")}
    
                elif node.type == "method_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_node = self._find_parent_class(node)
                        if class_node:
                            class_name = class_node.child_by_field_name("name").text.decode("utf-8")
                            method_name = name_node.text.decode("utf-8")
                            return {
                                "type": "method",
                                "name": f"{class_name}.{method_name}",
                            }
    
                elif node.type == "lexical_declaration":
                    for declarator in node.named_children:
                        if declarator.type == "variable_declarator":
                            name_node = declarator.child_by_field_name("name")
                            value_node = declarator.child_by_field_name("value")
                            if name_node and value_node:
                                name = name_node.text.decode("utf-8")
                                if value_node.type in ["arrow_function", "function_expression"]:
                                    body = value_node.child_by_field_name("body")
                                    has_jsx = any(
                                        child.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]
                                        for child in self._iter_tree(body or value_node)
                                    )
                                    logger.debug(f"Detected function {name}, has_jsx: {has_jsx}")
                                    return {
                                        "type": "component" if has_jsx else "function",
                                        "name": name,
                                        "code_end": value_node.end_byte,
                                    }
                                elif value_node.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]:
                                    return {
                                        "type": "component",
                                        "name": name,
                                    }
                                elif self._is_module_level(node) and not self._is_within_function(node):
                                    return {
                                        "type": "variable_definition",
                                        "name": name,
                                    }
    
                elif node.type == "export_statement":
                    declaration = node.child_by_field_name("declaration")
                    if declaration:
                        if declaration.type == "function_declaration":
                            name_node = declaration.child_by_field_name("name")
                            if name_node:
                                body = declaration.child_by_field_name("body")
                                has_jsx = any(
                                    child.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]
                                    for child in self._iter_tree(body or declaration)
                                )
                                logger.debug(f"Detected export function {name_node.text.decode('utf-8')}, has_jsx: {has_jsx}")
                                return {
                                    "type": "component" if has_jsx else "function",
                                    "name": name_node.text.decode("utf-8"),
                                }
                        elif declaration.type == "lexical_declaration":
                            for declarator in declaration.named_children:
                                if declarator.type == "variable_declarator":
                                    name_node = declarator.child_by_field_name("name")
                                    value_node = declarator.child_by_field_name("value")
                                    if name_node and value_node:
                                        name = name_node.text.decode("utf-8")
                                        if value_node.type in ["arrow_function", "function_expression"]:
                                            body = value_node.child_by_field_name("body")
                                            has_jsx = any(
                                                child.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]
                                                for child in self._iter_tree(body or value_node)
                                            )
                                            logger.debug(f"Detected export function {name}, has_jsx: {has_jsx}")
                                            return {
                                                "type": "component" if has_jsx else "function",
                                                "name": name,
                                                "code_end": value_node.end_byte,
                                            }
    
                elif node.type == "import_declaration" and self._is_module_level(node):
                    import_text = content[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
                    import_hash = hashlib.md5(import_text.encode()).hexdigest()[:8]
                    return {
                        "type": "import_statement",
                        "name": f"import_{import_hash}",
                        "import_text": import_text,
                    }
    
                elif (
                    node.type == "call_expression"
                    and node.child_by_field_name("function")
                    and node.child_by_field_name("function").type == "identifier"
                    and node.child_by_field_name("function").text.decode("utf-8") == "require"
                    and self._is_module_level(node)
                ):
                    require_text = content[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
                    require_hash = hashlib.md5(require_text.encode()).hexdigest()[:8]
                    return {
                        "type": "import_statement",
                        "name": f"require_{require_hash}",
                        "import_text": require_text,
                    }
    
            # Java-specific handling
            elif lang_name == "java":
                if node.type == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        class_node = self._find_parent_class(node)
                        if class_node:
                            class_name = class_node.child_by_field_name("name").text.decode("utf-8")
                            method_name = name_node.text.decode("utf-8")
                            return {
                                "type": "method",
                                "name": f"{class_name}.{method_name}",
                            }
                        else:
                            return {
                                "type": "function",
                                "name": name_node.text.decode("utf-8"),
                            }
    
                elif node.type == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        return {"type": "class", "name": name_node.text.decode("utf-8")}
    
                elif node.type == "import_declaration" and self._is_module_level(node):
                    import_text = content[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
                    import_hash = hashlib.md5(import_text.encode()).hexdigest()[:8]
                    return {
                        "type": "import_statement",
                        "name": f"import_{import_hash}",
                        "import_text": import_text,
                    }
    
                elif node.type == "field_declaration" and self._is_module_level(node):
                    declarator = node.child_by_field_name("declarator")
                    if declarator and declarator.child_by_field_name("name"):
                        var_name = declarator.child_by_field_name("name").text.decode("utf-8")
                        return {
                            "type": "variable_definition",
                            "name": var_name,
                        }
    
        except Exception as e:
            logger.error(f"Error getting element info: {e}")
    
        return None

    def _find_parent_class(self, node) -> Optional[object]:
        """Find the parent class node of a method node."""
        current = node
        while current:
            if current.type in ["class_definition", "class_declaration"]:
                return current
            current = current.parent
        return None

    def _get_source_context(self, node, content: bytes) -> Dict:
        """Get the source code context for a node."""
        try:
            # Get the full line containing the reference
            lines = content.decode("utf-8", errors="replace").splitlines()
            line_idx = node.start_point[0]
            if 0 <= line_idx < len(lines):
                source_code = lines[line_idx]

                # Get a few lines before and after for context
                start_idx = max(0, line_idx - 2)
                end_idx = min(len(lines), line_idx + 3)
                context_lines = lines[start_idx:end_idx]
                source_code = "\n".join(context_lines)

                return {
                    "source_code": source_code,
                    "source_location": {
                        "file": os.path.relpath(self.current_file, self.repo_path),
                        "start_line": node.start_point[0] + 1,
                        "start_col": node.start_point[1],
                        "end_line": node.end_point[0] + 1,
                        "end_col": node.end_point[1],
                    },
                }
        except Exception as e:
            logger.error(f"Error getting source context: {e}")

        return {
            "source_code": "",
            "source_location": {
                "file": "",
                "start_line": 0,
                "start_col": 0,
                "end_line": 0,
                "end_col": 0,
            },
        }

    def _find_dependencies(
    self,
    node,
    content: bytes,
    elements_by_name: Dict,
    lang_name: str,
    current_element_id: str = None,
    ) -> Dict:
        dependencies = {
            "tree": {
                "functions": {},
                "classes": {},
                "variables": {},
                "calls": [],
                "inheritance": [],
                "references": [],
            }
        }
    
        if not current_element_id:
            for name, element in elements_by_name.items():
                if element.get("node") == node or (
                    element.get("start_line") == node.start_point[0] + 1
                    and element.get("start_col") == node.start_point[1]
                    and element.get("end_line") == node.end_point[0] + 1
                    and element.get("end_col") == node.end_point[1]
                ):
                    current_element_id = element.get("id")
                    current_element_type = element.get("type")
                    break
    
        if lang_name == "python":
            query_str = """
            (call_expression
              function: (identifier) @function.call)
            (import_statement
              name: (dotted_name) @import.name)
            (import_from_statement
              name: (dotted_name) @import.from)
            (class_definition
              (superclasses
                (argument_list
                  (identifier) @class.inherit)))
            (identifier) @variable.ref
            """
        elif lang_name in ["javascript", "typescript", "tsx", "jsx"]:
            query_str = """
            (call_expression
              function: (identifier) @function.call)
            (call_expression
              function: (member_expression
                object: (identifier)
                property: (property_identifier) @method.call))
            (jsx_element
              open_tag: (jsx_opening_element
                name: (identifier) @component.use))
            (jsx_self_closing_element
              name: (identifier) @component.use)
            (call_expression
              function: (identifier) @hook.call
              (#match? @hook.call "^use[A-Z]"))
            (import_declaration
              (import_clause
                [(identifier) @import.name
                 (named_imports
                   (import_specifier
                     name: (identifier) @import.name))]))
            (class_declaration
              (superclass (identifier) @class.inherit))
            (identifier) @variable.ref
            """
        else:
            query_str = """
            (call_expression
              function: (identifier) @function.call)
            (import_statement
              name: (dotted_name) @import.name)
            (import_from_statement
              name: (dotted_name) @import.from)
            (class_definition
              (superclasses
                (argument_list
                  (identifier) @class.inherit)))
            (identifier) @variable.ref
            """
    
        try:
            logger.debug(f"Applying query for {lang_name} on node {node.type}")
            query = self.languages[lang_name].query(query_str)
            captures = query.captures(node)
            for capture_node, capture_name in captures:
                try:
                    name = capture_node.text.decode("utf-8", errors="replace")
                    logger.debug(f"Captured {name} as {capture_name} at line {capture_node.start_point[0] + 1}")
                    if capture_name == "component.use":
                        self._extract_component_usage(capture_node, content, elements_by_name, dependencies, current_element_id)
                    elif capture_name == "hook.call":
                        self._extract_hook_usage(capture_node, content, elements_by_name, dependencies, current_element_id)
                    elif capture_name == "function.call":
                        self._extract_function_calls(capture_node, content, elements_by_name, dependencies, current_element_id)
                    elif capture_name == "import.name":
                        self._extract_import_usage(capture_node, content, elements_by_name, dependencies, current_element_id)
                    elif capture_name == "variable.ref":
                        self._extract_variable_references(capture_node, content, elements_by_name, dependencies, current_element_id)
                    elif capture_name == "class.inherit":
                        self._extract_class_references(capture_node, content, elements_by_name, dependencies, current_element_id)
                except Exception as e:
                    logger.error(f"Error processing capture {capture_name}: {e}")
    
            logger.debug(f"Manual traversal for {node.type}")
            self._extract_function_calls(node, content, elements_by_name, dependencies, current_element_id)
            self._extract_variable_references(node, content, elements_by_name, dependencies, current_element_id)
            self._extract_class_references(node, content, elements_by_name, dependencies, current_element_id)
            self._extract_component_usage(node, content, elements_by_name, dependencies, current_element_id)
            self._extract_import_usage(node, content, elements_by_name, dependencies, current_element_id)
            self._extract_hook_usage(node, content, elements_by_name, dependencies, current_element_id)
    
            if current_element_type != "import_statement":
                element_code = ""
                for name, element in elements_by_name.items():
                    if element.get("id") == current_element_id:
                        element_code = element.get("code", "")
                        break
    
                for name, element in elements_by_name.items():
                    if element.get("type") == "import_statement":
                        if element["id"] == current_element_id:
                            continue
                        import_text = element.get("code", "")
                        imported_names = []
    
                        if lang_name == "python":
                            if import_text.startswith("from "):
                                try:
                                    parts = import_text.split(" import ")
                                    if len(parts) == 2:
                                        module_name = parts[0].replace("from ", "").strip()
                                        imports_part = parts[1].strip()
                                        if "," in imports_part:
                                            for item in imports_part.split(","):
                                                item = item.strip()
                                                if " as " in item:
                                                    item = item.split(" as ")[1].strip()
                                                imported_names.append(item)
                                        else:
                                            item = imports_part
                                            if " as " in item:
                                                item = item.split(" as ")[1].strip()
                                            imported_names.append(item)
                                        if "." in module_name:
                                            base_module = module_name.split(".")[0]
                                            imported_names.append(base_module)
                                except Exception:
                                    pass
                            elif import_text.startswith("import "):
                                try:
                                    imports_part = import_text.replace("import ", "").strip()
                                    if "," in imports_part:
                                        for item in imports_part.split(","):
                                            item = item.strip()
                                            if " as " in item:
                                                item = item.split(" as ")[1].strip()
                                            if "." in item:
                                                base_module = item.split(".")[0]
                                                imported_names.append(base_module)
                                            else:
                                                imported_names.append(item)
                                    else:
                                        item = imports_part
                                        if " as " in item:
                                            item = item.split(" as ")[1].strip()
                                        if "." in item:
                                            base_module = item.split(".")[0]
                                            imported_names.append(base_module)
                                        else:
                                            imported_names.append(item)
                                except Exception:
                                    pass
                        elif lang_name in ["javascript", "typescript", "tsx", "jsx"]:
                            if "import {" in import_text:
                                try:
                                    import_part = import_text.split("{")[1].split("}")[0]
                                    for part in import_part.split(","):
                                        name_part = part.strip()
                                        if " as " in name_part:
                                            name_part = name_part.split(" as ")[1]
                                        imported_names.append(name_part)
                                except Exception:
                                    pass
                            elif "import " in import_text and " from " in import_text:
                                try:
                                    default_import = import_text.split("import ")[1].split(" from ")[0].strip()
                                    imported_names.append(default_import)
                                except Exception:
                                    pass
                            elif "require(" in import_text:
                                try:
                                    variable_part = import_text.split("=")[0].strip()
                                    if "const " in variable_part:
                                        variable_part = variable_part.replace("const ", "")
                                    elif "let " in variable_part:
                                        variable_part = variable_part.replace("let ", "")
                                    elif "var " in variable_part:
                                        variable_part = variable_part.replace("var ", "")
                                    imported_names.append(variable_part)
                                except Exception:
                                    pass
                            elif "import " in import_text and " from " not in import_text:
                                imported_names.append("*")
    
                        is_used = False
                        for imported_name in imported_names:
                            if imported_name == "*" or imported_name in element_code:
                                is_used = True
                                break
    
                        if is_used:
                            if not any(ref.get("id") == element["id"] for ref in dependencies["tree"]["references"]):
                                dependencies["tree"]["references"].append(
                                    {
                                        "name": name,
                                        "type": "import_reference",
                                        "id": element.get("id", ""),
                                        "file": element.get("file_path", ""),
                                        "line": element.get("start_line", 0),
                                        "context": "import_dependency",
                                        "code": element.get("code", ""),
                                        "source_location": {
                                            "file": element.get("file_path", ""),
                                            "start_line": element.get("start_line", 0),
                                            "start_col": element.get("start_col", 0),
                                            "end_line": element.get("end_line", 0),
                                            "end_col": element.get("end_col", 0),
                                        },
                                    }
                                )
    
            if lang_name == "python" and current_element_type == "class":
                if node.type == "class_definition":
                    superclass_node = node.child_by_field_name("superclasses")
                    if superclass_node:
                        for child in superclass_node.children:
                            if child.type == "identifier":
                                superclass_name = child.text.decode("utf-8", errors="replace")
                                if superclass_name in elements_by_name:
                                    superclass_element = elements_by_name[superclass_name]
                                    if superclass_element.get("id") != current_element_id:
                                        if not any(
                                            inherit.get("id") == superclass_element.get("id")
                                            for inherit in dependencies["tree"]["inheritance"]
                                        ):
                                            dependencies["tree"]["inheritance"].append(
                                                {
                                                    "id": superclass_element.get("id", ""),
                                                    "name": superclass_name,
                                                    "type": "class",
                                                    "file": superclass_element.get("file_path", ""),
                                                    "line": superclass_element.get("start_line", 0),
                                                    "context": "inheritance",
                                                    "source_code": superclass_name,
                                                    "code": superclass_element.get("code", ""),
                                                    "source_location": {
                                                        "file": os.path.relpath(self.current_file, self.repo_path),
                                                        "start_line": child.start_point[0] + 1,
                                                        "start_col": child.start_point[1],
                                                        "end_line": child.end_point[0] + 1,
                                                        "end_col": child.end_point[1],
                                                    },
                                                }
                                            )
    
        except Exception as e:
            logger.error(f"Error extracting dependencies: {e}")
    
        logger.debug(f"Dependencies for {current_element_id}: {dependencies['tree']}")
        return dependencies

    def _is_within_function(self, node) -> bool:
        current = node
        while current and current.type != "program":
            if current.type in [
                "function_declaration",
                "arrow_function",
                "function_expression",
                "method_definition",
                "function"
            ]:
                return True
            current = current.parent
        return False

    def _get_element_code(self, element_id, elements_by_name):
        """Get the code for an element by ID."""
        for name, element in elements_by_name.items():
            if element.get("id") == element_id:
                return element.get("code", "")
        return ""

    def _extract_builtin_imports(
        self, node, content, dependencies, current_element_id=None
    ):
        """Extract built-in imports manually from the AST."""
        try:
            # Look for import statements
            if node.type == "import_statement" or node.type == "import_from_statement":
                # Get the whole import statement
                import_text = content[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                # Add to references
                dependencies["tree"]["references"].append(
                    {
                        "name": import_text.strip(),
                        "type": "import",
                        "context": "import_statement",
                        "source_code": import_text,
                        "code": import_text,  # For imports, the code is the import statement itself
                        "source_location": {
                            "file": os.path.relpath(self.current_file, self.repo_path),
                            "start_line": node.start_point[0] + 1,
                            "start_col": node.start_point[1],
                            "end_line": node.end_point[0] + 1,
                            "end_col": node.end_point[1],
                        },
                    }
                )

            # Recursively check children
            for child in node.children:
                self._extract_builtin_imports(
                    child, content, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting imports: {e}")

    def _extract_function_calls(
    self, node, content, elements_by_name, dependencies, current_element_id=None
):
        try:
            if node.type in ["call_expression", "call"]:
                func_node = node.child_by_field_name("function")
                func_name = None
                if func_node:
                    if func_node.type == "identifier":
                        func_name = func_node.text.decode("utf-8", errors="replace")
                    elif func_node.type in ["attribute", "member_expression"]:
                        func_name = content[func_node.start_byte : func_node.end_byte].decode("utf-8", errors="replace")
    
                if func_name and func_name in elements_by_name:
                    element = elements_by_name[func_name]
                    if element.get("id") != current_element_id:
                        call_code = content[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                        logger.debug(f"Captured function call {func_name} at line {node.start_point[0] + 1}")
                        dependencies["tree"]["functions"][func_name] = {
                            "id": element.get("id", ""),
                            "name": func_name,
                            "type": element.get("type", "function"),
                            "file": element.get("file_path", ""),
                            "line": element.get("start_line", 0),
                            "context": "function_call",
                            "source_code": call_code,
                            "code": element.get("code", ""),
                            "source_location": {
                                "file": os.path.relpath(self.current_file, self.repo_path),
                                "start_line": node.start_point[0] + 1,
                                "start_col": node.start_point[1],
                                "end_line": node.end_point[0] + 1,
                                "end_col": node.end_point[1],
                            },
                        }
    
            for child in node.children:
                self._extract_function_calls(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting function calls: {e}")

    def _extract_variable_references(
        self, node, content, elements_by_name, dependencies, current_element_id=None
    ):
        """Extract variable references manually from the AST."""
        try:
            # Look for identifiers that might be variables
            if node.type == "identifier":
                var_name = node.text.decode("utf-8", errors="replace")
                if var_name in elements_by_name:
                    element = elements_by_name[var_name]

                    # Get the ID of the current element if not provided
                    if not current_element_id:
                        for name, elem in elements_by_name.items():
                            if elem.get("node") == node:
                                current_element_id = elem.get("id")
                                break

                    # Skip if this is a self-reference
                    if element.get("id") == current_element_id:
                        return

                    var_ref_code = content[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="replace"
                    )

                    # Get the actual variable definition code
                    element_code = element.get("code", "")

                    # Add variable reference to dependencies if not already there
                    if var_name not in dependencies["tree"]["variables"]:
                        dependencies["tree"]["variables"][var_name] = {
                            "id": element.get("id", ""),
                            "name": var_name,
                            "type": "variable",
                            "file": element.get("file_path", ""),
                            "line": element.get("start_line", 0),
                            "context": "variable_reference",
                            "source_code": var_ref_code,  # How the variable is referenced
                            "code": element_code,  # The actual variable definition
                            "source_location": {
                                "file": os.path.relpath(
                                    self.current_file, self.repo_path
                                ),
                                "start_line": node.start_point[0] + 1,
                                "start_col": node.start_point[1],
                                "end_line": node.end_point[0] + 1,
                                "end_col": node.end_point[1],
                            },
                        }

            # Recursively check children
            for child in node.children:
                self._extract_variable_references(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting variable references: {e}")

    def _extract_class_references(
        self, node, content, elements_by_name, dependencies, current_element_id=None
    ):
        """Extract class references manually from the AST."""
        try:
            # Look for class references (identifiers that match class names)
            if node.type == "identifier":
                class_name = node.text.decode("utf-8", errors="replace")
                if (
                    class_name in elements_by_name
                    and elements_by_name[class_name].get("type") == "class"
                ):
                    element = elements_by_name[class_name]

                    # Get the ID of the current element if not provided
                    if not current_element_id:
                        for name, elem in elements_by_name.items():
                            if elem.get("node") == node:
                                current_element_id = elem.get("id")
                                break

                    # Skip if this is a self-reference
                    if element.get("id") == current_element_id:
                        return

                    class_ref_code = content[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="replace"
                    )

                    # Get the actual class definition code
                    element_code = element.get("code", "")

                    # Add class reference to dependencies if not already there
                    if class_name not in dependencies["tree"]["classes"]:
                        dependencies["tree"]["classes"][class_name] = {
                            "id": element.get("id", ""),
                            "name": class_name,
                            "type": "class",
                            "file": element.get("file_path", ""),
                            "line": element.get("start_line", 0),
                            "context": "class_reference",
                            "source_code": class_ref_code,  # How the class is referenced
                            "code": element_code,  # The actual class definition
                            "source_location": {
                                "file": os.path.relpath(
                                    self.current_file, self.repo_path
                                ),
                                "start_line": node.start_point[0] + 1,
                                "start_col": node.start_point[1],
                                "end_line": node.end_point[0] + 1,
                                "end_col": node.end_point[1],
                            },
                        }

                    # Check for class inheritance
                    parent = node.parent
                    if (
                        parent
                        and parent.type == "argument_list"
                        and parent.parent
                        and parent.parent.type == "class_definition"
                    ):
                        # This is a class that inherits from the referenced class
                        # Skip if this is a self-reference
                        if element.get("id") == current_element_id:
                            return

                        inheritance_code = content[
                            node.start_byte : node.end_byte
                        ].decode("utf-8", errors="replace")
                        dependencies["tree"]["inheritance"].append(
                            {
                                "id": element.get("id", ""),
                                "name": class_name,
                                "type": "class",
                                "file": element.get("file_path", ""),
                                "line": element.get("start_line", 0),
                                "context": "inheritance",
                                "source_code": inheritance_code,  # How the inheritance is declared
                                "code": element_code,  # The actual parent class definition
                                "source_location": {
                                    "file": os.path.relpath(
                                        self.current_file, self.repo_path
                                    ),
                                    "start_line": node.start_point[0] + 1,
                                    "start_col": node.start_point[1],
                                    "end_line": node.end_point[0] + 1,
                                    "end_col": node.end_point[1],
                                },
                            }
                        )

            # Recursively check children
            for child in node.children:
                self._extract_class_references(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting class references: {e}")

    # --- Added: New method to extract JSX component usage ---

    def _extract_component_usage(
        self, node, content, elements_by_name, dependencies, current_element_id=None
    ):
        try:
            if node.type in ["jsx_element", "jsx_self_closing_element"]:
                name_node = None
                if node.type == "jsx_element":
                    opening_element = node.child_by_field_name("open_tag")
                    if opening_element:
                        name_node = opening_element.child_by_field_name("name")
                else:
                    name_node = node.child_by_field_name("name")

                if name_node and name_node.type == "identifier":
                    component_name = name_node.text.decode("utf-8", errors="replace")
                    component_code = content[node.start_byte : node.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if component_name in elements_by_name:
                        element = elements_by_name[component_name]
                        if element.get("id") != current_element_id:
                            dependencies["tree"]["references"].append(
                                {
                                    "name": component_name,
                                    "type": "component_reference",
                                    "id": element.get("id", ""),
                                    "file": element.get("file_path", ""),
                                    "line": element.get("start_line", 0),
                                    "context": "component_usage",
                                    "code": element.get("code", ""),
                                    "source_location": {
                                        "file": os.path.relpath(
                                            self.current_file, self.repo_path
                                        ),
                                        "start_line": node.start_point[0] + 1,
                                        "start_col": node.start_point[1],
                                        "end_line": node.end_point[0] + 1,
                                        "end_col": node.end_point[1],
                                    },
                                }
                            )
                    else:
                        # External component (e.g., Marker)
                        dependencies["tree"]["references"].append(
                            {
                                "name": component_name,
                                "type": "component_reference",
                                "id": "",
                                "file": "unknown",
                                "line": 0,
                                "context": "component_usage",
                                "code": component_code,
                                "source_location": {
                                    "file": os.path.relpath(
                                        self.current_file, self.repo_path
                                    ),
                                    "start_line": node.start_point[0] + 1,
                                    "start_col": node.start_point[1],
                                    "end_line": node.end_point[0] + 1,
                                    "end_col": node.end_point[1],
                                },
                            }
                        )

            for child in node.children:
                self._extract_component_usage(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting component usage: {e}")

    def _extract_import_usage(
        self, node, content, elements_by_name, dependencies, current_element_id=None
    ):
        try:
            if node.type == "import_declaration":
                clause = node.child_by_field_name("clause")
                source_node = node.child_by_field_name("source")
                if clause:
                    for child in clause.named_children:
                        if child.type in ["identifier", "named_imports"]:
                            if child.type == "named_imports":
                                for specifier in child.named_children:
                                    if specifier.type == "import_specifier":
                                        name_node = specifier.child_by_field_name(
                                            "name"
                                        )
                                        if name_node:
                                            name = name_node.text.decode("utf-8")
                                            import_code = content[
                                                node.start_byte : node.end_byte
                                            ].decode("utf-8", errors="replace")
                                            if name in elements_by_name:
                                                element = elements_by_name[name]
                                                if (
                                                    element.get("id")
                                                    != current_element_id
                                                ):
                                                    dependencies["tree"][
                                                        "references"
                                                    ].append(
                                                        {
                                                            "name": name,
                                                            "type": "import_reference",
                                                            "id": element.get("id", ""),
                                                            "file": element.get(
                                                                "file_path", ""
                                                            ),
                                                            "line": element.get(
                                                                "start_line", 0
                                                            ),
                                                            "context": "import_usage",
                                                            "code": element.get(
                                                                "code", ""
                                                            ),
                                                            "source_location": {
                                                                "file": os.path.relpath(
                                                                    self.current_file,
                                                                    self.repo_path,
                                                                ),
                                                                "start_line": node.start_point[
                                                                    0
                                                                ]
                                                                + 1,
                                                                "start_col": node.start_point[
                                                                    1
                                                                ],
                                                                "end_line": node.end_point[
                                                                    0
                                                                ]
                                                                + 1,
                                                                "end_col": node.end_point[
                                                                    1
                                                                ],
                                                            },
                                                        }
                                                    )
                                            else:
                                                # External import
                                                dependencies["tree"][
                                                    "references"
                                                ].append(
                                                    {
                                                        "name": name,
                                                        "type": "import_reference",
                                                        "id": "",
                                                        "file": "unknown",
                                                        "line": 0,
                                                        "context": "import_usage",
                                                        "code": import_code,
                                                        "source_location": {
                                                            "file": os.path.relpath(
                                                                self.current_file,
                                                                self.repo_path,
                                                            ),
                                                            "start_line": node.start_point[
                                                                0
                                                            ]
                                                            + 1,
                                                            "start_col": node.start_point[
                                                                1
                                                            ],
                                                            "end_line": node.end_point[
                                                                0
                                                            ]
                                                            + 1,
                                                            "end_col": node.end_point[
                                                                1
                                                            ],
                                                        },
                                                    }
                                                )
                            elif child.type == "identifier":
                                name = child.text.decode("utf-8")
                                import_code = content[
                                    node.start_byte : node.end_byte
                                ].decode("utf-8", errors="replace")
                                if name in elements_by_name:
                                    element = elements_by_name[name]
                                    if element.get("id") != current_element_id:
                                        dependencies["tree"]["references"].append(
                                            {
                                                "name": name,
                                                "type": "import_reference",
                                                "id": element.get("id", ""),
                                                "file": element.get("file_path", ""),
                                                "line": element.get("start_line", 0),
                                                "context": "import_usage",
                                                "code": element.get("code", ""),
                                                "source_location": {
                                                    "file": os.path.relpath(
                                                        self.current_file,
                                                        self.repo_path,
                                                    ),
                                                    "start_line": node.start_point[0]
                                                    + 1,
                                                    "start_col": node.start_point[1],
                                                    "end_line": node.end_point[0] + 1,
                                                    "end_col": node.end_point[1],
                                                },
                                            }
                                        )
                                else:
                                    # External import
                                    dependencies["tree"]["references"].append(
                                        {
                                            "name": name,
                                            "type": "import_reference",
                                            "id": "",
                                            "file": "unknown",
                                            "line": 0,
                                            "context": "import_usage",
                                            "code": import_code,
                                            "source_location": {
                                                "file": os.path.relpath(
                                                    self.current_file, self.repo_path
                                                ),
                                                "start_line": node.start_point[0] + 1,
                                                "start_col": node.start_point[1],
                                                "end_line": node.end_point[0] + 1,
                                                "end_col": node.end_point[1],
                                            },
                                        }
                                    )

            for child in node.children:
                self._extract_import_usage(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting import usage: {e}")

    def _extract_hook_usage(
        self, node, content, elements_by_name, dependencies, current_element_id=None
    ):
        try:
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node and func_node.type == "identifier":
                    func_name = func_node.text.decode("utf-8")
                    if func_name.startswith("use") and func_name[3].isupper():
                        hook_code = content[node.start_byte : node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        if func_name in elements_by_name:
                            element = elements_by_name[func_name]
                            if element.get("id") != current_element_id:
                                dependencies["tree"]["references"].append(
                                    {
                                        "name": func_name,
                                        "type": "hook_reference",
                                        "id": element.get("id", ""),
                                        "file": element.get("file_path", ""),
                                        "line": element.get("start_line", 0),
                                        "context": "hook_usage",
                                        "code": element.get("code", ""),
                                        "source_location": {
                                            "file": os.path.relpath(
                                                self.current_file, self.repo_path
                                            ),
                                            "start_line": node.start_point[0] + 1,
                                            "start_col": node.start_point[1],
                                            "end_line": node.end_point[0] + 1,
                                            "end_col": node.end_point[1],
                                        },
                                    }
                                )
                        else:
                            # External hook (e.g., useState)
                            dependencies["tree"]["references"].append(
                                {
                                    "name": func_name,
                                    "type": "hook_reference",
                                    "id": "",
                                    "file": "unknown",
                                    "line": 0,
                                    "context": "hook_usage",
                                    "code": hook_code,
                                    "source_location": {
                                        "file": os.path.relpath(
                                            self.current_file, self.repo_path
                                        ),
                                        "start_line": node.start_point[0] + 1,
                                        "start_col": node.start_point[1],
                                        "end_line": node.end_point[0] + 1,
                                        "end_col": node.end_point[1],
                                    },
                                }
                            )

            for child in node.children:
                self._extract_hook_usage(
                    child, content, elements_by_name, dependencies, current_element_id
                )
        except Exception as e:
            logger.error(f"Error extracting hook usage: {e}")

    def _parse_file(self, file_path: str) -> List[Dict]:
        lang_name = self._get_file_language(file_path)
        logger.info(f"File: {file_path}, exists: {os.path.exists(file_path)}, lang: {lang_name}")
        if not lang_name or lang_name not in self.languages:
            logger.info(f"Cannot parse {file_path}: Language {lang_name} not supported")
            return []
    
        try:
            with open(file_path, "rb") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return []
    
        self.parser.language = self.languages[lang_name]
        try:
            tree = self.parser.parse(content)
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return []
    
        logger.info(f"Parsing file: {file_path}")
        self.current_file = file_path
    
        code_elements = []
        elements_by_name = {}
        elements_by_id = {}
        component_scope = None
    
        for node in self._iter_tree(tree.root_node):
            element_info = self._get_element_info(node, content, lang_name)
            if element_info and element_info.get("name"):
                try:
                    code_end = element_info.get("code_end", node.end_byte)
                    element_code = content[node.start_byte : code_end].decode("utf-8", errors="replace")
                    rel_file_path = os.path.relpath(file_path, self.repo_path)
    
                    element = {
                        "type": element_info["type"],
                        "name": element_info["name"],
                        "code": element_code,
                        "start_line": node.start_point[0] + 1,
                        "start_col": node.start_point[1],
                        "end_line": node.end_point[0] + 1,
                        "end_col": node.end_point[1],
                        "file_path": rel_file_path,
                        "node": node,
                    }
    
                    element["code"] = self._format_code(element["code"])
                    element_id = self._generate_element_id(element)
                    element["id"] = element_id
    
                    if element_id in elements_by_id:
                        existing = elements_by_id[element_id]
                        if len(existing["code"]) > len(element["code"]):
                            continue
                        else:
                            code_elements = [e for e in code_elements if e["id"] != element_id]
                            del elements_by_name[existing["name"]]
                            del elements_by_id[element_id]
    
                    logger.debug(f"Processing element {element['name']} (type: {element['type']})")
                    if element["type"] == "component":
                        component_scope = element
                        elements_by_name[element_info["name"]] = element
                        elements_by_id[element_id] = element
                        code_elements.append(element)
                    elif element["type"] == "function":
                        elements_by_name[element_info["name"]] = element
                        elements_by_id[element_id] = element
                        if component_scope and (
                            node.start_point[0] >= component_scope["start_line"] - 1 and 
                            node.end_point[0] <= component_scope["end_line"]
                        ):
                            logger.debug(f"Storing {element['name']} as dependency for {component_scope['name']}")
                            # Store as dependency, not top-level
                            continue
                        code_elements.append(element)
                    else:
                        elements_by_name[element_info["name"]] = element
                        elements_by_id[element_id] = element
                        code_elements.append(element)
    
                except Exception as e:
                    logger.error(f"Error processing element {element_info['name']} in {file_path}: {e}")
                    continue
    
        all_dependencies = {}
        for element in code_elements:
            try:
                dependencies = self._find_dependencies(
                    element["node"], content, elements_by_name, lang_name, element["id"]
                )
                element["dependencies"] = dependencies
                all_dependencies[element["id"]] = dependencies
            except Exception as e:
                logger.error(f"Error finding dependencies for {element['name']}: {e}")
                element["dependencies"] = {
                    "tree": {
                        "functions": {},
                        "classes": {},
                        "variables": {},
                        "calls": [],
                        "inheritance": [],
                        "references": [],
                    }
                }
    
        direct_reference_tracking = {element["id"]: set() for element in code_elements}
        for element in code_elements:
            element["referenced_by"] = {
                "functions": {},
                "classes": {},
                "variables": {},
                "inheritance": [],
                "references": [],
            }
            for other_id, deps in all_dependencies.items():
                if other_id == element["id"]:
                    continue
                for category in ["functions", "classes", "variables"]:
                    for item_name, item_info in deps["tree"][category].items():
                        if item_info.get("id") == element["id"]:
                            other_element = elements_by_id.get(other_id)
                            if other_element and other_element["id"] != element["id"]:
                                direct_reference_tracking[element["id"]].add(other_id)
                                element["referenced_by"][category][other_element["name"]] = {
                                    "id": other_id,
                                    "name": other_element["name"],
                                    "type": other_element["type"],
                                    "file": other_element["file_path"],
                                    "line": other_element["start_line"],
                                    "context": f"referenced_by_{category[:-1]}",
                                    "code": other_element["code"],
                                    "source_location": {
                                        "file": other_element["file_path"],
                                        "start_line": other_element["start_line"],
                                        "start_col": other_element["start_col"],
                                        "end_line": other_element["end_line"],
                                        "end_col": other_element["end_col"],
                                    },
                                }
                for ref_info in deps["tree"]["references"]:
                    if ref_info.get("id") == element["id"]:
                        other_element = elements_by_id.get(other_id)
                        if other_element and other_element["id"] != element["id"]:
                            direct_reference_tracking[element["id"]].add(other_id)
                            element["referenced_by"]["references"].append({
                                "id": other_id,
                                "name": other_element["name"],
                                "type": other_element["type"],
                                "file": other_element["file_path"],
                                "line": other_element["start_line"],
                                "context": "referenced_by",
                                "code": other_element["code"],
                                "source_location": {
                                    "file": other_element["file_path"],
                                    "start_line": other_element["start_line"],
                                    "start_col": other_element["start_col"],
                                    "end_line": other_element["end_line"],
                                    "end_col": other_element["end_col"],
                                },
                            })
    
        for element in code_elements:
            dependencies = element["dependencies"]["tree"]
            self._remove_redundant_references(dependencies)
            self._remove_bidirectional_redundancies(element, direct_reference_tracking)
            self._verify_no_bidirectional_references(element)
    
        for element in code_elements:
            if "node" in element:
                del element["node"]
    
        logger.info(f"Found {len(code_elements)} code elements in {file_path}")
        return code_elements

    def _remove_redundant_references(self, dependencies):
        """Remove references that are already included in more specific categories."""
        # Collect IDs that are already in specific categories
        specific_ids = set()

        # Add IDs from functions
        for func_info in dependencies["functions"].values():
            if "id" in func_info:
                specific_ids.add(func_info["id"])

        # Add IDs from classes
        for class_info in dependencies["classes"].values():
            if "id" in class_info:
                specific_ids.add(class_info["id"])

        # Add IDs from variables
        for var_info in dependencies["variables"].values():
            if "id" in var_info:
                specific_ids.add(var_info["id"])

        # Add IDs from inheritance
        for inherit_info in dependencies["inheritance"]:
            if "id" in inherit_info:
                specific_ids.add(inherit_info["id"])

        # Remove references that are already in specific categories
        dependencies["references"] = [
            ref
            for ref in dependencies["references"]
            if "id" in ref and ref["id"] not in specific_ids
        ]

    def _remove_bidirectional_redundancies(self, element, direct_reference_tracking):
        """Remove bidirectional redundancies between dependencies and referenced_by."""
        # Get this element's dependencies and ID
        dependencies = element["dependencies"]["tree"]
        element_id = element["id"]

        # Get the set of elements that directly reference this element
        direct_references = direct_reference_tracking.get(element_id, set())

        # Filter out references in dependencies that refer to elements that already reference this element
        new_references = []
        for ref in dependencies["references"]:
            ref_id = ref.get("id")
            # Only keep reference if:
            # 1. It has a valid ID
            # 2. The ID is not the current element (no self-references)
            # 3. The ID is not in the direct references set (no bidirectional references)
            if ref_id and ref_id != element_id and ref_id not in direct_references:
                new_references.append(ref)
        dependencies["references"] = new_references

        # Remove from functions dictionary
        functions_to_remove = []
        for func_name, func_info in dependencies["functions"].items():
            # Check if this is a self-reference or bidirectional reference
            if (
                func_info.get("id") == element_id
                or func_info.get("id") in direct_references
            ):
                functions_to_remove.append(func_name)
        for func_name in functions_to_remove:
            del dependencies["functions"][func_name]

        # Remove from classes dictionary
        classes_to_remove = []
        for class_name, class_info in dependencies["classes"].items():
            # Check if this is a self-reference or bidirectional reference
            if (
                class_info.get("id") == element_id
                or class_info.get("id") in direct_references
            ):
                classes_to_remove.append(class_name)
        for class_name in classes_to_remove:
            del dependencies["classes"][class_name]

        # Remove from variables dictionary
        variables_to_remove = []
        for var_name, var_info in dependencies["variables"].items():
            # Check if this is a self-reference or bidirectional reference
            if (
                var_info.get("id") == element_id
                or var_info.get("id") in direct_references
            ):
                variables_to_remove.append(var_name)
        for var_name in variables_to_remove:
            del dependencies["variables"][var_name]

        # Filter inheritance list
        dependencies["inheritance"] = [
            inherit
            for inherit in dependencies["inheritance"]
            if inherit.get("id") != element_id
            and inherit.get("id") not in direct_references
        ]

        # Final verification: ensure dependencies and referenced_by are fully disjoint
        self._verify_no_bidirectional_references(element)

    def _verify_no_bidirectional_references(self, element):
        """Final verification to ensure no bidirectional references exist."""
        dependencies = element["dependencies"]["tree"]
        referenced_by = element["referenced_by"]

        # Collect all IDs from referenced_by sections
        referenced_by_ids = set()

        # Functions
        for func_info in referenced_by["functions"].values():
            if "id" in func_info:
                referenced_by_ids.add(func_info["id"])

        # Classes
        for class_info in referenced_by["classes"].values():
            if "id" in class_info:
                referenced_by_ids.add(class_info["id"])

        # Variables
        for var_info in referenced_by["variables"].values():
            if "id" in var_info:
                referenced_by_ids.add(var_info["id"])

        # Inheritance
        for inherit_info in referenced_by["inheritance"]:
            if "id" in inherit_info:
                referenced_by_ids.add(inherit_info["id"])

        # References
        for ref_info in referenced_by["references"]:
            if "id" in ref_info:
                referenced_by_ids.add(ref_info["id"])

        # Check and fix any remaining dependencies that refer to something in referenced_by
        self._clean_dependencies_with_ids(dependencies["functions"], referenced_by_ids)
        self._clean_dependencies_with_ids(dependencies["classes"], referenced_by_ids)
        self._clean_dependencies_with_ids(dependencies["variables"], referenced_by_ids)

        # Clean lists
        dependencies["inheritance"] = [
            inherit
            for inherit in dependencies["inheritance"]
            if "id" in inherit and inherit["id"] not in referenced_by_ids
        ]

        dependencies["references"] = [
            ref
            for ref in dependencies["references"]
            if "id" in ref and ref["id"] not in referenced_by_ids
        ]

    def _clean_dependencies_with_ids(self, dependency_dict, id_set):
        """Remove entries from dependency dict if their ID is in id_set."""
        keys_to_remove = []
        for key, info in dependency_dict.items():
            if "id" in info and info["id"] in id_set:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del dependency_dict[key]

    def _is_module_level(self, node) -> bool:
        """Check if a node is at module level (not inside a function or method)."""
        current = node.parent
        while current:
            if current.type in [
                "function_definition",
                "method_definition",
                "function_declaration",
            ]:
                return False
            current = current.parent
        return True

    def analyze_repository(self) -> Dict[str, Any]:
        logger.info(f"Starting repository analysis at {self.repo_path}")

        all_code_elements = []
        processed_files = []
        global_elements_by_name = {}

        # First pass: collect all elements
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [
                d for d in dirs if not self._should_exclude_path(os.path.join(root, d))
            ]
            for file in files:
                file_path = os.path.join(root, file)
                if self._should_exclude_path(file_path):
                    continue
                lang_name = self._get_file_language(file_path)
                if not lang_name or lang_name not in self.languages:
                    continue
                try:
                    elements = self._parse_file(file_path)
                    all_code_elements.extend(elements)
                    processed_files.append(os.path.relpath(file_path, self.repo_path))
                    for element in elements:
                        global_elements_by_name[element["name"]] = element
                except Exception as e:
                    logger.error(f"Error processing file {file_path}: {e}")

        # Second pass: update dependencies with global elements
        for element in all_code_elements:
            try:
                with open(
                    os.path.join(self.repo_path, element["file_path"]), "rb"
                ) as f:
                    content = f.read()
                lang_name = self._get_file_language(
                    os.path.join(self.repo_path, element["file_path"])
                )
                self.parser.language = self.languages[lang_name]
                tree = self.parser.parse(content)
                node = None
                for n in self._iter_tree(tree.root_node):
                    if (
                        n.start_point[0] + 1 == element["start_line"]
                        and n.start_point[1] == element["start_col"]
                        and n.end_point[0] + 1 == element["end_line"]
                        and n.end_point[1] == element["end_col"]
                    ):
                        node = n
                        break
                if node:
                    element["dependencies"] = self._find_dependencies(
                        node, content, global_elements_by_name, lang_name, element["id"]
                    )
                else:
                    logger.warning(
                        f"Node not found for element {element['name']} in {element['file_path']}"
                    )
            except Exception as e:
                logger.error(f"Error updating dependencies for {element['name']}: {e}")
                element["dependencies"] = {
                    "tree": {
                        "functions": {},
                        "classes": {},
                        "variables": {},
                        "calls": [],
                        "inheritance": [],
                        "references": [],
                    }
                }

        # Third pass: add back-references
        direct_reference_tracking = {
            element["id"]: set() for element in all_code_elements
        }
        for element in all_code_elements:
            element["referenced_by"] = {
                "functions": {},
                "classes": {},
                "variables": {},
                "inheritance": [],
                "references": [],
            }
            for other_element in all_code_elements:
                if other_element["id"] == element["id"]:
                    continue
                deps = other_element["dependencies"]
                for category in ["functions", "classes", "variables"]:
                    for item_name, item_info in deps["tree"][category].items():
                        if item_info.get("id") == element["id"]:
                            direct_reference_tracking[element["id"]].add(
                                other_element["id"]
                            )
                            element["referenced_by"][category][
                                other_element["name"]
                            ] = {
                                "id": other_element["id"],
                                "name": other_element["name"],
                                "type": other_element["type"],
                                "file": other_element["file_path"],
                                "line": other_element["start_line"],
                                "context": f"referenced_by_{category[:-1]}",
                                "code": other_element["code"],
                                "source_location": {
                                    "file": other_element["file_path"],
                                    "start_line": other_element["start_line"],
                                    "start_col": other_element["start_col"],
                                    "end_line": other_element["end_line"],
                                    "end_col": other_element["end_col"],
                                },
                            }
                for ref_info in deps["tree"]["references"]:
                    if ref_info.get("id") == element["id"]:
                        other_element = elements_by_id.get(other_id)
                        if other_element and other_element["id"] != element["id"]:
                            direct_reference_tracking[element["id"]].add(
                                other_element["id"]
                            )
                            element["referenced_by"]["references"].append(
                                {
                                    "id": other_element["id"],
                                    "name": other_element["name"],
                                    "type": other_element["type"],
                                    "file": other_element["file_path"],
                                    "line": other_element["start_line"],
                                    "context": "referenced_by",
                                    "code": other_element["code"],
                                    "source_location": {
                                        "file": other_element["file_path"],
                                        "start_line": other_element["start_line"],
                                        "start_col": other_element["start_col"],
                                        "end_line": other_element["end_line"],
                                        "end_col": other_element["end_col"],
                                    },
                                }
                            )

        for element in all_code_elements:
            dependencies = element["dependencies"]["tree"]
            self._remove_redundant_references(dependencies)
            self._remove_bidirectional_redundancies(element, direct_reference_tracking)
            self._verify_no_bidirectional_references(element)

        for element in all_code_elements:
            if "node" in element:
                del element["node"]

        result = {
            "elements": all_code_elements,
            "metadata": {
                "last_analysis": datetime.datetime.now().isoformat(),
                "total_elements": len(all_code_elements),
                "processed_files": processed_files,
            },
        }

        try:
            with open(ELEMENTS_DB_PATH, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Analysis results saved to {ELEMENTS_DB_PATH}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

        logger.info(
            f"Analysis complete. Found {len(all_code_elements)} code elements in {len(processed_files)} files"
        )
        return result


def main():
    """Main entry point."""
    try:
        # Create GitHub Actions workflow output group
        print("::group::Code Analysis")

        logger.info("Starting code analysis...")
        analyzer = CodeAnalyzer(REPO_PATH)
        results = analyzer.analyze_repository()

        # Print summary
        print(f"\nAnalysis completed successfully:")
        print(f"- Total code elements: {results['metadata']['total_elements']}")
        print(f"- Files processed: {len(results['metadata']['processed_files'])}")
        print(f"- Results saved to: {ELEMENTS_DB_PATH}")

        # End GitHub Actions group
        print("::endgroup::")

    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
