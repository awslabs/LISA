"""Set environment variables for cert locations in Lambda function."""
import os

region_name = os.environ["AWS_REGION"]
if "iso" in region_name:
    cacerts_directory = "/etc/pki/ca-trust/extracted/pem"
    merged_cert_filename = os.path.join(cacerts_directory, "tls-ca-bundle.pem")
    os.environ["AWS_CA_BUNDLE"] = merged_cert_filename
    os.environ["REQUESTS_CA_BUNDLE"] = merged_cert_filename
    os.environ["SSL_CERT_FILE"] = merged_cert_filename
    os.environ["SSL_CERT_DIR"] = cacerts_directory
