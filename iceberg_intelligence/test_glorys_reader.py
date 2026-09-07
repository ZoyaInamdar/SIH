from iceberg_wrapper.glorys_reader import create_glorys_reader

reader = create_glorys_reader()

print("\nGLORYS reader created successfully!")
print(reader)
print("\nReader variables:")
print(reader.variables)