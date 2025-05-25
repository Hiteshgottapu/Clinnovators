<?php
$servername = "localhost";
$username = "root";
$password = "";
$dbname = "medscript";

// Create connection
$conn = new mysqli($servername, $username, $password, $dbname);

// Check connection
if ($conn->connect_error) {
    die("Connection failed: " . $conn->connect_error);
}

// Get form data
$email = $_POST['email'];

// Check if email exists
$sql = "SELECT * FROM users WHERE email='$email'";
$result = $conn->query($sql);

if ($result->num_rows > 0) {
    // User exists, generate reset token
    $token = bin2hex(random_bytes(50));
    $expiry = date("Y-m-d H:i:s", strtotime('+1 hour'));

    // Store token in database
    $sql = "UPDATE users SET reset_token='$token', reset_expiry='$expiry' WHERE email='$email'";
    if ($conn->query($sql) === TRUE) {
        // Send reset email
        $resetLink = "http://localhost/reset-password-form.php?token=$token";
        $subject = "Password Reset Request";
        $message = "Click the following link to reset your password: $resetLink";
        $headers = "From: no-reply@yourdomain.com";

        if (mail($email, $subject, $message, $headers)) {
            echo "Password reset link has been sent to your email.";
        } else {
            echo "Failed to send email.";
        }
    } else {
        echo "Error updating record: " . $conn->error;
    }
} else {
    echo "No user found with that email address.";
}

$conn->close();
?>