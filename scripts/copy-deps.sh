#!/bin/bash

function install_python_deps() {
    local input_path=$1
    local output_path=$2
    local package=$3

    echo "Installing Python dependencies for $package"
    mkdir -p "${output_path}"
    if ! pip install -r ${input_path}/requirements.txt --target $output_path --platform manylinux2014_x86_64 --only-binary=:all: --no-deps --no-cache-dir; then
        echo "Failed to install Python dependencies for ${package}"
        exit 1
    fi

    echo "${package} dependencies installed successfully"
    rsync -a "${input_path}/" "${output_path}"

    echo "Optimizing ${package}"
    find $output_path -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
    find $output_path -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null
    find $output_path -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
    find $output_path -type f -name "*.pyc" -delete
    find $output_path -type f -name "*.pyo" -delete
    find $output_path -type f -name "*.so" -exec strip {} + 2>/dev/null
}

function setup_python_dist(){
    cd dist

    # Define the layers
    PYTHON_VERSION="3.13"
    DIST="."
    OUTPUT_DIR="python/lib/${PYTHON_VERSION}/site-packages"

    # Create a virtual environment for isolation
    python -m venv .venv
    source .venv/bin/activate

    # # Install dependencies for each lambda layer
    layers=("authorizer" "common" "fastapi")
    layers_path="../lib/core/layers"
    layers_output="${DIST}/lambdaLayer"
    for layer in "${layers[@]}"; do
        layer_path="${layers_path}/${layer}"
        layer_output="${layers_output}/${layer}/${OUTPUT_DIR}"
        install_python_deps $layer_path $layer_output $layer
    done

    # Install rag layer
    rag_path="../lib/rag/layer"
    rag_output="${DIST}/rag/${OUTPUT_DIR}"
    rag_package="rag"
    install_python_deps $rag_path $rag_output $rag_package

    # Install lisa-sdk dependencies
    sdk_path="../lisa-sdk"
    sdk_output="${DIST}/lisa-sdk/${OUTPUT_DIR}"
    sdk_package="lisa-sdk"
    install_python_deps $sdk_path $sdk_output $sdk_package

    # Install rest-api for lisa-serve
    rest_path="../lib/serve/rest-api/src"
    rest_output="${DIST}/rest-api/${OUTPUT_DIR}"
    rest_package="rest-api"
    install_python_deps $rest_path $rest_output $rest_package

    # Install instructor embedding
    instructor_path="../lib/serve/instructor/src"
    instructor_output="${DIST}/instructor/${OUTPUT_DIR}"
    instructor_package="instructor"
    install_python_deps $instructor_path $instructor_output $instructor_package

    # Deactivate virtual environment
    deactivate
    rm -rf .venv
    echo "All Python dependencies installed successfully"
    cd -
}

function copy_dist() {
    mkdir -p dist/ecs_model_deployer && rsync -av ecs_model_deployer/dist dist/ecs_model_deployer/ && cp ecs_model_deployer/Dockerfile dist/ecs_model_deployer/
    mkdir -p dist/vector_store_deployer && rsync -av vector_store_deployer/dist dist/vector_store_deployer/ && cp vector_store_deployer/Dockerfile dist/vector_store_deployer/
    mkdir -p dist/lisa-web && rsync -av lib/user-interface/react/dist/ dist/lisa-web
    mkdir -p dist/docs && rsync -av lib/docs/dist/ dist/docs
    cp VERSION dist/
}

mkdir -p dist
# setup_python_dist
copy_dist
