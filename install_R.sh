#!/bin/bash
set -ex
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh;
bash miniconda.sh -b -p $HOME/miniconda
export PATH="$HOME/miniconda/bin:$PATH"
hash -r
conda config --set always_yes yes --set changeps1 no
conda update -q conda
conda info -a
conda create -q -n test-env python=$TRAVIS_PYTHON_VERSION
source activate test-env
conda install -c bioconda pysam
conda install -c anaconda pandas
conda install -c anaconda biopython
conda install -c anaconda numpydoc
conda install -c anaconda matplotlib 
conda install -c anaconda rpy2