# PythonScriptSync
This library allows a list to be shared real time between 2 scripts using files (Unix domain sockets)

Example use:
```python
# Script Number 1

from script_sync import *
synced_list = SList("File1", "File2")

# once this list is created the second script should be run before performing anything on the list so they can sync

synced_list.append(3)
synced_list.extend([2,3,4])

print(synced_list[1]) # outputs 2
```
```python
# Script Number 2

from script_sync import *
synced_list = SList("File1", "File2")

input("")
print(synced_list) # outputs [3,2,3,4] assuming script1 has finished
```
