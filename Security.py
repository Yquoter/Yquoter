import os

# --- Configuration Settings ---
PROJECT_NAME = "Yquoter"
CONTACT_EMAIL = "yodeeshi@gmail.com"  # Replace with actual contact email
SUPPORTED_VERSION = "0.1.0"  # Example version range for security updates


# --- English Markdown Template ---
SECURITY_TEMPLATE = f"""
# {PROJECT_NAME} Security Policy

## Supported Versions

We commit to providing security updates for the following versions. Please use the latest version whenever possible.

| Version   | Supported          |
|-----------|--------------------|
| {SUPPORTED_VERSION} | :white_check_mark: |
| < 1.0     | :x:                |

## Reporting a Vulnerability

We take the security of **{PROJECT_NAME}** seriously. If you discover a security vulnerability in the project, we appreciate your help and ask that you disclose it responsibly.

**Do not submit security vulnerabilities through public GitHub Issues.**

Please report discovered vulnerabilities to us privately using the following method:

1. **Send an email** to: **`{CONTACT_EMAIL}`**
2. Use the email subject format: `[SECURITY] {PROJECT_NAME} Vulnerability Report: <brief description>`
3. Include as much detail as possible in your report:
   * A description of the vulnerability and its potential impact
   * Detailed steps to reproduce the vulnerability (including code examples, configurations, etc.)
   * The version of **{PROJECT_NAME}** you are using

After receiving your report, we will confirm the issue, provide an initial response within one business day, and keep you informed about our remediation plan and progress. We sincerely appreciate all researchers who help improve the security of **{PROJECT_NAME}**.
"""


def generate_security_md():
    """
    Main function to generate the SECURITY.md file.
    Handles file creation with proper error handling and user feedback.
    """
    file_name = "SECURITY.md"

    print(f"Generating {file_name} file...")

    try:
        # Write the security policy with UTF-8 encoding to support special characters
        with open(file_name, "w", encoding="utf-8") as f:
            f.write(SECURITY_TEMPLATE.strip())
        print(f"✅ File {file_name} generated successfully in the project root directory!")

    except IOError as e:
        print(f"❌ Error: Unable to write to file {file_name}.")
        print(f"   Reason: {e}")


# Execute the generation function when the script is run directly
if __name__ == "__main__":
    # Validate contact email configuration before generating
    if "[yodeeshi@gmail.com]" == CONTACT_EMAIL:  # Check for default placeholder
        print("⚠️ Warning: Please update the CONTACT_EMAIL variable with a valid email address first!")
    else:
        generate_security_md()
