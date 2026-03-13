"""
Unit tests for app/file_processors/content_minimizer.py

Tests comment and docstring removal from Python and YAML files
to minimize token usage while preserving functionality.
"""

import pytest


class TestRemovePythonCommentsAndDocstrings:
    """Test remove_python_comments_and_docstrings function."""
    
    def test_remove_single_line_comment(self):
        """Test removing single-line comments."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = """
def hello():
    # This is a comment
    print("hello")
"""
        result = remove_python_comments_and_docstrings(code)
        
        assert "# This is a comment" not in result
        assert 'print("hello")' in result
    
    def test_remove_docstring(self):
        """Test removing docstrings."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = '''
def hello():
    """This is a docstring."""
    print("hello")
'''
        result = remove_python_comments_and_docstrings(code)
        
        assert "This is a docstring" not in result
        assert 'print("hello")' in result
    
    def test_preserve_code_structure(self):
        """Test preserving code structure."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = """
def func1():
    pass

def func2():
    pass
"""
        result = remove_python_comments_and_docstrings(code, preserve_structure=True)
        
        assert "def func1():" in result
        assert "def func2():" in result
    
    def test_handle_inline_comments(self):
        """Test handling inline comments."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = 'x = 10  # This is inline comment'
        result = remove_python_comments_and_docstrings(code)
        
        assert "x = 10" in result
        assert "# This is inline comment" not in result
    
    def test_preserve_hash_in_strings(self):
        """Test preserving # inside strings."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = 'text = "This is a #hashtag"'
        result = remove_python_comments_and_docstrings(code)
        
        # Should preserve # in string
        assert "#hashtag" in result
    
    def test_handle_syntax_error(self):
        """Test handling code with syntax errors."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        # Invalid Python code
        code = "def invalid syntax here"
        
        # Should not crash, returns original or cleaned comments
        result = remove_python_comments_and_docstrings(code)
        assert isinstance(result, str)
    
    def test_remove_class_docstring(self):
        """Test removing class docstrings."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = '''
class MyClass:
    """Class docstring."""
    
    def method(self):
        """Method docstring."""
        pass
'''
        result = remove_python_comments_and_docstrings(code)
        
        assert "Class docstring" not in result
        assert "Method docstring" not in result
        assert "class MyClass:" in result
    
    def test_empty_code(self):
        """Test handling empty code."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        result = remove_python_comments_and_docstrings("")
        assert result == ""
    
    def test_no_preserve_structure(self):
        """Test without preserving structure."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = """
# Comment 1

# Comment 2

def func():
    pass
"""
        result = remove_python_comments_and_docstrings(code, preserve_structure=False)
        
        # Should have fewer blank lines
        assert result.count('\n\n\n') == 0


class TestRemoveYamlComments:
    """Test remove_yaml_comments function."""
    
    def test_remove_full_line_comment(self):
        """Test removing full-line YAML comments."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = """
# This is a comment
key: value
another: data
"""
        result = remove_yaml_comments(yaml)
        
        assert "# This is a comment" not in result
        assert "key: value" in result
    
    def test_remove_inline_comment(self):
        """Test removing inline YAML comments."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = "key: value  # inline comment"
        result = remove_yaml_comments(yaml)
        
        assert "key: value" in result
        assert "# inline comment" not in result
    
    def test_preserve_yaml_structure(self):
        """Test preserving YAML structure."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = """
section1:
  key1: value1
  key2: value2
section2:
  key3: value3
"""
        result = remove_yaml_comments(yaml)
        
        assert "section1:" in result
        assert "section2:" in result
        assert "key1: value1" in result
    
    def test_preserve_hash_in_quoted_string(self):
        """Test preserving # in quoted strings."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = 'key: "value with # inside"'
        result = remove_yaml_comments(yaml)
        
        # Should preserve # in string
        assert "# inside" in result
    
    def test_empty_yaml(self):
        """Test handling empty YAML."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        result = remove_yaml_comments("")
        assert result == ""
    
    def test_only_comments(self):
        """Test YAML with only comments."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = """
# Comment 1
# Comment 2
# Comment 3
"""
        result = remove_yaml_comments(yaml)
        
        # Should be empty or only whitespace
        assert result.strip() == ""


class TestShouldMinimizeFile:
    """Test should_minimize_file function."""
    
    def test_python_file_should_minimize(self):
        """Test that Python files should be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("test.py") is True
        assert should_minimize_file("module.py") is True
        assert should_minimize_file("/path/to/script.py") is True
    
    def test_yaml_file_should_minimize(self):
        """Test that YAML files should be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("config.yml") is True
        assert should_minimize_file("config.yaml") is True
    
    def test_other_source_files_should_minimize(self):
        """Test that other source files should be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("script.js") is True
        assert should_minimize_file("app.ts") is True
        assert should_minimize_file("Main.java") is True
        assert should_minimize_file("program.go") is True
    
    def test_markdown_should_not_minimize(self):
        """Test that Markdown files should not be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("README.md") is False
        assert should_minimize_file("docs.md") is False
    
    def test_readme_should_not_minimize(self):
        """Test that README files should not be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("README") is False
        assert should_minimize_file("readme.txt") is False
        assert should_minimize_file("ReadMe.md") is False
    
    def test_other_doc_files_should_not_minimize(self):
        """Test that documentation files should not be minimized."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("CHANGELOG.md") is False
        assert should_minimize_file("LICENSE") is False
        assert should_minimize_file("CONTRIBUTING.md") is False
        assert should_minimize_file("file.txt") is False
        assert should_minimize_file("doc.html") is False
    
    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("Script.PY") is True
        assert should_minimize_file("CONFIG.YML") is True
        assert should_minimize_file("README.MD") is False
    
    def test_unknown_extension(self):
        """Test unknown file extensions."""
        from app.file_processors.content_minimizer import should_minimize_file
        
        assert should_minimize_file("file.xyz") is False
        assert should_minimize_file("data.bin") is False


class TestEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_python_with_triple_quotes_in_code(self):
        """Test handling triple quotes in actual code."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = '''
text = """This is a string, not a docstring"""
print(text)
'''
        result = remove_python_comments_and_docstrings(code)
        
        # Should preserve the string
        assert 'text =' in result
        assert 'print(text)' in result
    
    def test_python_with_multiple_docstrings(self):
        """Test removing multiple docstrings."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        code = '''
"""Module docstring."""

def func1():
    """Function 1 docstring."""
    pass

def func2():
    """Function 2 docstring."""
    pass
'''
        result = remove_python_comments_and_docstrings(code)
        
        assert "Module docstring" not in result
        assert "Function 1 docstring" not in result
        assert "Function 2 docstring" not in result
    
    def test_yaml_with_complex_comments(self):
        """Test YAML with complex comment patterns."""
        from app.file_processors.content_minimizer import remove_yaml_comments
        
        yaml = """
key1: value1  # Comment 1
# Full line comment
key2: value2
  # Indented comment
  subkey: subvalue  # Another inline
"""
        result = remove_yaml_comments(yaml)
        
        assert "# Comment 1" not in result
        assert "# Full line comment" not in result
        assert "# Indented comment" not in result
        assert "key1: value1" in result
        assert "key2: value2" in result
    
    def test_very_long_code(self):
        """Test handling very long code."""
        from app.file_processors.content_minimizer import remove_python_comments_and_docstrings
        
        # Generate long code with comments
        lines = []
        for i in range(100):
            lines.append(f"# Comment {i}")
            lines.append(f"x{i} = {i}")
        
        code = '\n'.join(lines)
        result = remove_python_comments_and_docstrings(code)
        
        # Should remove all comments
        assert "# Comment" not in result
        # Should keep assignments
        assert "x0 = 0" in result
        assert "x99 = 99" in result
