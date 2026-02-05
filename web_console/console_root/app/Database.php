<?php
/**
 * Database abstraction wrapper
 * Handles all database operations with prepared statements
 */
class Database {
    private $pdo;
    private $host;
    private $user;
    private $pass;
    private $name;

    public function __construct($host, $user, $pass, $name) {
        $this->host = $host;
        $this->user = $user;
        $this->pass = $pass;
        $this->name = $name;
    }

    /**
     * Connect to the database
     */
    public function connect() {
        try {
            $dsn = "mysql:host={$this->host};dbname={$this->name};charset=utf8mb4";
            $this->pdo = new PDO(
                $dsn,
                $this->user,
                $this->pass,
                [
                    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
                    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
                    PDO::ATTR_EMULATE_PREPARES => false,
                ]
            );
            return true;
        } catch (PDOException $e) {
            error_log("Database connection error: " . $e->getMessage());
            throw $e;
        }
    }

    /**
     * Check if connected
     */
    public function isConnected() {
        return $this->pdo !== null;
    }

    /**
     * Execute a query with prepared statement
     *
     * @param string $sql SQL query with ? placeholders
     * @param array $params Values to bind to placeholders
     * @return PDOStatement
     */
    public function query($sql, $params = []) {
        if (!$this->isConnected()) {
            throw new Exception("Database not connected");
        }

        try {
            $stmt = $this->pdo->prepare($sql);
            $stmt->execute($params);
            return $stmt;
        } catch (PDOException $e) {
            error_log("Query error: " . $e->getMessage());
            throw $e;
        }
    }

    /**
     * Fetch a single row
     */
    public function fetchOne($sql, $params = []) {
        $stmt = $this->query($sql, $params);
        return $stmt->fetch();
    }

    /**
     * Fetch all rows
     */
    public function fetchAll($sql, $params = []) {
        $stmt = $this->query($sql, $params);
        return $stmt->fetchAll();
    }

    /**
     * Insert a row and return last insert ID
     */
    public function insert($table, $data) {
        $columns = implode(',', array_keys($data));
        $placeholders = implode(',', array_fill(0, count($data), '?'));
        $sql = "INSERT INTO $table ($columns) VALUES ($placeholders)";

        $this->query($sql, array_values($data));
        return $this->pdo->lastInsertId();
    }

    /**
     * Update rows
     */
    public function update($table, $data, $where, $where_params = []) {
        $set = implode(',', array_map(fn($k) => "$k=?", array_keys($data)));
        $sql = "UPDATE $table SET $set WHERE $where";

        $params = array_merge(array_values($data), $where_params);
        $stmt = $this->query($sql, $params);
        return $stmt->rowCount();
    }

    /**
     * Delete rows
     */
    public function delete($table, $where, $where_params = []) {
        $sql = "DELETE FROM $table WHERE $where";
        $stmt = $this->query($sql, $where_params);
        return $stmt->rowCount();
    }
}
