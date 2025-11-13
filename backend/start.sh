#!/usr/bin/env bash
gunicorn main:app -b 0.0.0.0:$PORT

