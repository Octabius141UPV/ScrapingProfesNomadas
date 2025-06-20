import smtplib
from email.mime.text import MIMEText

# Cambia estos valores por los tuyos
from_email = "pruebaprofesnomadas@gmail.com"
from_password = "xynbyjmpoffxfdej"
to_email = "raulforteabusiness@gmail.com"

msg = MIMEText("Esto es una prueba de envío SMTP desde Python con acentos y eñes: á, é, í, ó, ú, ñ.", _charset="utf-8")
msg["Subject"] = "Prueba SMTP"
msg["From"] = from_email
msg["To"] = to_email

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(from_email, from_password)
    server.sendmail(from_email, to_email, msg.as_string())
    server.quit()
    print("¡Correo enviado correctamente!")
except Exception as e:
    print("Error:", e)
