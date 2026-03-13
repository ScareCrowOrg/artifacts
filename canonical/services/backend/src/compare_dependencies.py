import toml

requirements_file = "requirements.txt"
pyproject_file = "pyproject.toml"

def parse_requirements(file_path):
    """Parse requirements.txt and return a dictionary of dependencies with versions."""
    dependencies = {}
    with open(file_path, "r") as file:
        for line in file:
            dep = line.strip()
            if dep and not dep.startswith("#"):
                if "==" in dep:
                    name, version = dep.split("==")
                    dependencies[name] = version
                else:
                    dependencies[dep] = None  # No version specified
    return dependencies

def parse_pyproject(file_path):
    """Parse pyproject.toml and return a dictionary of dependencies with versions."""
    with open(file_path, "r") as file:
        pyproject_data = toml.load(file)
        dependencies = {}
        for dep, version in pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
            if dep != "python":  # Exclude Python version specification
                if isinstance(version, str):
                    dependencies[dep] = version
                else:
                    dependencies[dep] = None  # No version specified
        return dependencies

def compare_dependencies():
    """Compare dependencies between requirements.txt and pyproject.toml."""
    req_deps = parse_requirements(requirements_file)
    pyproject_deps = parse_pyproject(pyproject_file)

    missing_in_pyproject = set(req_deps) - set(pyproject_deps)
    extra_in_pyproject = set(pyproject_deps) - set(req_deps)
    differing_versions = {
        dep: (req_deps[dep], pyproject_deps[dep])
        for dep in req_deps
        if dep in pyproject_deps and req_deps[dep] != pyproject_deps[dep]
    }

    print("Dependencies missing in pyproject.toml:")
    for dep in missing_in_pyproject:
        version = req_deps[dep]
        print(f"- {dep}=={version}" if version else f"- {dep}")

    print("\nDependencies extra in pyproject.toml:")
    for dep in extra_in_pyproject:
        version = pyproject_deps[dep]
        print(f"- {dep}=={version}" if version else f"- {dep}")

    print("\nDependencies with differing versions:")
    for dep, (req_version, pyproject_version) in differing_versions.items():
        print(f"- {dep}: requirements.txt has {req_version}, pyproject.toml has {pyproject_version}")

if __name__ == "__main__":
    compare_dependencies()