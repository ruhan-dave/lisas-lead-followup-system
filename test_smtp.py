#!/usr/bin/env python3
"""Comprehensive SMTP diagnostics."""
import socket
import smtplib
import sys

sys.path.insert(0, '.')
from config.settings import SMTPConfig, EmailConfig, SystemConfig

print('=== CONFIG LOADED ===')
print(f'SMTP_HOST: {SMTPConfig.SMTP_HOST}')
print(f'SMTP_PORT: {SMTPConfig.SMTP_PORT}')
print(f'SMTP_USER: {SMTPConfig.SMTP_USER}')
print(f'EMAIL_FROM_ADDRESS: {EmailConfig.FROM_ADDRESS}')
print(f'EMAIL_FROM_NAME: {EmailConfig.FROM_NAME}')
print(f'DRY_RUN: {SystemConfig.DRY_RUN}')
print()

print('=== DNS RESOLUTION ===')
try:
    ip = socket.gethostbyname(SMTPConfig.SMTP_HOST)
    print(f'✓ {SMTPConfig.SMTP_HOST} resolves to {ip}')
except Exception as e:
    print(f'✗ DNS resolution failed: {e}')
print()

print('=== TCP PORT CONNECTIVITY ===')
for hostname in [SMTPConfig.SMTP_HOST, 'mail.spacemail.com']:
    print(f'Testing {hostname}:')
    for port in [587, 465]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((hostname, port))
            sock.close()
            if result == 0:
                print(f'  ✓ Port {port} is OPEN')
            else:
                print(f'  ✗ Port {port} is CLOSED (error code: {result})')
        except Exception as e:
            print(f'  ✗ Port {port} connection failed: {e}')
print()

print('=== SMTP HANDSHAKE (no auth) ===')
try:
    if SMTPConfig.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTPConfig.SMTP_HOST, SMTPConfig.SMTP_PORT, timeout=10)
        print(f'✓ SMTP_SSL connection established')
    else:
        server = smtplib.SMTP(SMTPConfig.SMTP_HOST, SMTPConfig.SMTP_PORT, timeout=10)
        server.ehlo()
        print(f'✓ EHLO successful')
        if server.has_extn('starttls'):
            print('✓ STARTTLS supported')
            server.starttls()
            print('✓ TLS connection established')
            server.ehlo()
            print('✓ EHLO over TLS successful')
    server.quit()
    print('✓ SMTP handshake complete')
except Exception as e:
    print(f'✗ SMTP handshake failed: {e}')
print()

print('=== SMTP AUTHENTICATION TEST ===')
try:
    if SMTPConfig.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTPConfig.SMTP_HOST, SMTPConfig.SMTP_PORT, timeout=10)
    else:
        server = smtplib.SMTP(SMTPConfig.SMTP_HOST, SMTPConfig.SMTP_PORT, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
    server.login(SMTPConfig.SMTP_USER, SMTPConfig.SMTP_PASSWORD)
    print(f'✓ Authentication successful for {SMTPConfig.SMTP_USER}')
    server.quit()
except Exception as e:
    print(f'✗ Authentication failed: {e}')
