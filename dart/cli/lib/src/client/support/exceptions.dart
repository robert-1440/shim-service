

class ShimException {
  final String message;

  ShimException(this.message);

  @override
  String toString() {
    return message;
  }
}

class UserAlreadyLoggedInException extends ShimException {
  final String token;

  UserAlreadyLoggedInException(this.token) : super("User already logged in.");
}

class SessionGoneException extends ShimException {
  SessionGoneException() : super("Session is gone.");
}
