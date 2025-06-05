import os
import sys
import tiktoken_ext.openai_public  # Assuming this is the correct import

def main():
    # Ensure the script gets a valid argument for 'TIKTOKEN_CACHE_DIR'
    if len(sys.argv) < 2:
        print("Error: You must provide the 'TIKTOKEN_CACHE_DIR' as the first argument.")
        sys.exit(1)
    
    # Set the environment variable 'TIKTOKEN_CACHE_DIR' to the first argument
    os.environ['TIKTOKEN_CACHE_DIR'] = sys.argv[1]
    print(f"Environment variable 'TIKTOKEN_CACHE_DIR' set to: {os.environ['TIKTOKEN_CACHE_DIR']}")

    # Iterate over the encoding constructors in 'tiktoken_ext.openai_public.ENCODING_CONSTRUCTORS'
    for name, func in tiktoken_ext.openai_public.ENCODING_CONSTRUCTORS.items():
        print(f"Calling function '{name}':")
        func()  # Call the function

if __name__ == "__main__":
    main()