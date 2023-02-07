# compile kaitai

& $env:KAITAI -t python -d '.\igni' '.\kaitai\mdb.ksy'

# install igni to python directory

$igni_dir = $env:IGNI_PYTHON_BASE + '\Lib\igni'

if (Test-Path -Path $igni_dir) {
    Remove-Item -Recurse -Force $igni_dir
}

Copy-Item -Force -Recurse '.\igni' -Destination ($env:IGNI_PYTHON_BASE + '\Lib\')
