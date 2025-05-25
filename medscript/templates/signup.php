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
$user = $_POST['username'];
$email = $_POST['email'];
$pass = $_POST['password'];

// Hash the password
$hashed_password = password_hash($pass, PASSWORD_DEFAULT);

// Insert data into database
$sql = "INSERT INTO users (username, email, password) VALUES ('$user', '$email', '$hashed_password')";

if ($conn->query($sql) === TRUE) {
    echo "New record created successfully";
} else {
    echo "Error: " . $sql . "<br>" . $conn->error;
}

$conn->close();
?>