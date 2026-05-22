import imaplib

server = 'ssl0.ovh.net'
port = 993
user = 'contact@exregister.io'
password = 'Ex!!052026**Man%%RegV51'

print(f"Connecting to IMAP {server}:{port}...")
try:
    mail = imaplib.IMAP4_SSL(server, port)
    mail.login(user, password)
    print("Login successful!")
    
    mail.select('inbox')
    
    # Search for all emails
    status, messages = mail.search(None, 'ALL')
    if status == 'OK':
        mail_ids = messages[0].split()
        print(f"Found {len(mail_ids)} total emails in inbox.")
        
        # Mark the last 5 emails as UNSEEN (unread)
        last_ids = mail_ids[-5:]
        for mail_id in last_ids:
            mail.store(mail_id, '-FLAGS', '\\Seen')
            print(f"Marked mail ID {mail_id.decode()} as UNSEEN.")
    else:
        print("Could not search mailbox.")
        
    mail.close()
    mail.logout()
    print("Connection closed.")
except Exception as e:
    print("Error:", e)
