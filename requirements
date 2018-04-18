#!/bin/bash
cd `dirname $0`; PACKAGE_PATH=`pwd`; IFS='/'; read -ra ARR <<< "$PACKAGE_PATH"; IFS=';'; N=`expr ${#ARR[*]} - 1`; PACKAGE_NAME=${ARR[$N]}
source venv
pip freeze | egrep --invert-match "\b$PACKAGE_NAME\b" >requirements.txt
