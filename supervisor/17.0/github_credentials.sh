#!/bin/bash

while getopts u:p:t:e: flag
do
    case "${flag}" in
        u) username=${OPTARG};;
        p) password=${OPTARG};;
        t) token=${OPTARG};;
        e) email=${OPTARG};;
        *) echo "Use -u username -p password -t token -e email";;
    esac
done
git config --global credential.helper "cache --timeout=3600"
git config --global user.name "$username"
git config --global user.password "$password"
git config --global user.email "$email"
git config --global url.https://git:$token@github.com/.insteadOf git@github.com:
