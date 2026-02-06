<?php
/**
 * Login page - authentication form and handler
 */

session_start();

// Include config
require_once __DIR__ . '/../config/config.php';
require_once __DIR__ . '/../app/Database.php';

// If already logged in, redirect to dashboard
if (isset($_SESSION['username'])) {
    header('Location: /');
    exit;
}

$error_message = '';
$username_value = '';

// Handle form submission
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';
    $username_value = htmlspecialchars($username, ENT_QUOTES, 'UTF-8');

    // Validate input
    if (empty($username) || empty($password)) {
        $error_message = 'Username and password are required.';
    } elseif ($username === CONSOLE_USERNAME && password_verify($password, CONSOLE_PASSWORD_HASH)) {
        // Authentication successful
        session_regenerate_id(true);
        $_SESSION['username'] = $username;
        $_SESSION['user_id'] = session_id();
        $_SESSION['login_time'] = time();
        $_SESSION['last_activity'] = time();

        // Log to database if available
        try {
            $db = new Database(DB_HOST, DB_USER, DB_PASS, DB_NAME);
            $db->connect();
            $db->execute(
                "INSERT INTO audit_log_t (actor, action, target_type, target_id, details_json) VALUES (?, ?, ?, ?, ?)",
                [
                    $username,
                    'LOGIN',
                    'user_session',
                    session_id(),
                    json_encode([
                        'ip_address' => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
                        'user_agent' => $_SERVER['HTTP_USER_AGENT'] ?? 'unknown',
                    ])
                ]
            );
        } catch (Exception $e) {
            error_log("Audit log failed: " . $e->getMessage());
            // Continue anyway - don't block login
        }

        header('Location: /');
        exit;
    } else {
        // Invalid credentials - use generic message to avoid user enumeration
        $error_message = 'Invalid username or password.';
    }
}

// Check for session timeout message
$show_expired = isset($_GET['expired']) && $_GET['expired'] === '1';
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Cornerstone Archive Console</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
            width: 100%;
            max-width: 400px;
            padding: 40px;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            font-size: 24px;
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
        }
        .login-header p {
            color: #666;
            font-size: 14px;
        }
        .form-control {
            margin-bottom: 20px;
            border-radius: 5px;
            padding: 10px 15px;
            border: 1px solid #ddd;
        }
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .btn-login {
            width: 100%;
            padding: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 5px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.3s;
        }
        .btn-login:hover {
            opacity: 0.9;
            color: white;
        }
        .alert {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>Cornerstone Archive</h1>
            <p>Console Administration</p>
        </div>

        <?php if ($show_expired): ?>
            <div class="alert alert-warning" role="alert">
                <strong>Session Expired</strong><br>
                Your session has timed out. Please log in again.
            </div>
        <?php endif; ?>

        <?php if ($error_message): ?>
            <div class="alert alert-danger" role="alert">
                <?php echo htmlspecialchars($error_message, ENT_QUOTES, 'UTF-8'); ?>
            </div>
        <?php endif; ?>

        <form method="POST">
            <div class="mb-3">
                <label for="username" class="form-label">Username</label>
                <input type="text" class="form-control" id="username" name="username"
                       value="<?php echo $username_value; ?>" required autofocus>
            </div>

            <div class="mb-3">
                <label for="password" class="form-label">Password</label>
                <input type="password" class="form-control" id="password" name="password" required>
            </div>

            <button type="submit" class="btn btn-login">Log In</button>
        </form>

        <div style="text-align: center; margin-top: 20px; color: #999; font-size: 12px;">
            <p>Cornerstone Archive Console v1.0.0</p>
        </div>
    </div>
</body>
</html>
