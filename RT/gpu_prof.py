"""
A simple script that uses the GPUProfiler and inserts a profile Object onto a
result Object from `send_data.py`.
"""

from sys import argv
from json import load, dump

from .core.gpu_profiler import GPUProfiler, ProfileResponse

if __name__ == '__main__':
    if (len(argv)) < 3: exit(1)
    
    profile = argv[1] # Which profile to inject
    logfile = argv[2] # The `res.json` file to inject the profile to
    
    # Initiate a GPUProfiler instance, compute table
    gpu: GPUProfiler     = GPUProfiler(profile, 0.25)
    res: ProfileResponse = gpu.compute() 

    if res is None: exit(1) # logged internally

    with open(logfile, 'r+') as file:
        # Load current state of the file and update 'data' section
        ctx = load(file)
        try:
            ctx['data'].update(res)
        except Exception:
            print(f'Cannot update: {logfile}: {Exception}')

        file.seek(0)              # Navigate to the beginning
        dump(ctx, file, indent=4) # Dump updated JSON 
        file.truncate()           # Resize byte number
