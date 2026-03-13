import toml

pyproject_file = "pyproject.toml"

def find_duplicates(file_path):
    """Find duplicate dependencies in pyproject.toml."""
    with open(file_path, "r") as file:
        pyproject_data = toml.load(file)
        dependencies = pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})

        seen = {}
        duplicates = {}

        for dep, version in dependencies.items():
            if dep in seen:
                duplicates[dep] = (seen[dep], version)
            else:
                seen[dep] = version

        return duplicates

def main():
    duplicates = find_duplicates(pyproject_file)

    if duplicates:
        print("Duplicate dependencies found:")
        for dep, versions in duplicates.items():
            print(f"- {dep}: {versions[0]} and {versions[1]}")
    else:
        print("No duplicate dependencies found.")

if __name__ == "__main__":
    main()