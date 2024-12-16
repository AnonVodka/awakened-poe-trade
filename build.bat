@echo off
echo Building renderer
cd renderer
call yarn build 
cd ../main
echo Building main app
call yarn build
echo Bundling app
set CSC_NAME="Certificate name in Keychain"
call yarn package
cd ../