#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import sys

import tiktoken_ext.openai_public  # Assuming this is the correct import


def main() -> None:
    # Ensure the script gets a valid argument for 'TIKTOKEN_CACHE_DIR'
    if len(sys.argv) < 2:
        print("Error: You must provide the 'TIKTOKEN_CACHE_DIR' as the first argument.")
        sys.exit(1)

    # Set the environment variable 'TIKTOKEN_CACHE_DIR' to the first argument
    os.environ["TIKTOKEN_CACHE_DIR"] = sys.argv[1]
    print(f"Environment variable 'TIKTOKEN_CACHE_DIR' set to: {os.environ['TIKTOKEN_CACHE_DIR']}")

    # Check if the TIKTOKEN_CACHE_DIR already exists
    if not os.path.exists(os.environ["TIKTOKEN_CACHE_DIR"]):
        # Iterate over the encoding constructors in 'tiktoken_ext.openai_public.ENCODING_CONSTRUCTORS'
        for name, func in tiktoken_ext.openai_public.ENCODING_CONSTRUCTORS.items():
            print(f"Calling function '{name}':")
            func()  # Call the function


if __name__ == "__main__":
    main()
