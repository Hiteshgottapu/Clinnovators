<?php
$servername = "localhostlocalhost\SQLEXPRESS";
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
$user = $_POST['username'];
$pass = $_POST['password'];

// Check if user exists
$sql = "SELECT * FROM users WHERE username='$user'";
$result = $conn->query($sql);

if ($result->num_rows > 0) {
    // User exists, verify password
    $row = $result->fetch_assoc();
    if (password_verify($pass, $row['password'])) {
        echo "Login successful!";
        // Redirect to a protected page or set session variables
    } else {
        echo "Invalid password.";
    }
} else {
    echo "No user found with that username.";
}

$conn->close();
?>