/**
 * Form Validation Utilities
 */

/**
 * Validate email format
 */
export const isValidEmail = (email) => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

/**
 * Validate password strength
 * At least 8 characters, 1 uppercase, 1 lowercase, 1 number
 */
export const isValidPassword = (password) => {
  return (
    password.length >= 8 &&
    /[A-Z]/.test(password) &&
    /[a-z]/.test(password) &&
    /[0-9]/.test(password)
  );
};

/**
 * Validate username (alphanumeric and underscores, 3-20 chars)
 */
export const isValidUsername = (username) => {
  const usernameRegex = /^[a-zA-Z0-9_]{3,20}$/;
  return usernameRegex.test(username);
};

/**
 * Login form validation
 */
export const validateLoginForm = (values) => {
  const errors = {};

  if (!values.username) {
    errors.username = "Username or email is required";
  }

  if (!values.password) {
    errors.password = "Password is required";
  }

  return errors;
};

/**
 * Signup form validation
 */
export const validateSignupForm = (values) => {
  const errors = {};

  if (!values.username) {
    errors.username = "Username is required";
  } else if (!isValidUsername(values.username)) {
    errors.username =
      "Username must be 3-20 characters (letters, numbers, underscores only)";
  }

  if (!values.email) {
    errors.email = "Email is required";
  } else if (!isValidEmail(values.email)) {
    errors.email = "Please enter a valid email address";
  }

  if (!values.password) {
    errors.password = "Password is required";
  } else if (!isValidPassword(values.password)) {
    errors.password =
      "Password must be at least 8 characters with uppercase, lowercase, and number";
  }

  if (!values.password_confirm) {
    errors.password_confirm = "Please confirm your password";
  } else if (values.password !== values.password_confirm) {
    errors.password_confirm = "Passwords do not match";
  }

  return errors;
};

/**
 * Profile update validation
 */
export const validateProfileForm = (values) => {
  const errors = {};

  if (values.email && !isValidEmail(values.email)) {
    errors.email = "Please enter a valid email address";
  }

  if (values.first_name && values.first_name.length < 2) {
    errors.first_name = "First name must be at least 2 characters";
  }

  if (values.last_name && values.last_name.length < 2) {
    errors.last_name = "Last name must be at least 2 characters";
  }

  return errors;
};

/**
 * Change password validation
 */
export const validateChangePasswordForm = (values) => {
  const errors = {};

  if (!values.old_password) {
    errors.old_password = "Current password is required";
  }

  if (!values.new_password) {
    errors.new_password = "New password is required";
  } else if (!isValidPassword(values.new_password)) {
    errors.new_password =
      "Password must be at least 8 characters with uppercase, lowercase, and number";
  }

  if (!values.new_password_confirm) {
    errors.new_password_confirm = "Please confirm your new password";
  } else if (values.new_password !== values.new_password_confirm) {
    errors.new_password_confirm = "Passwords do not match";
  }

  return errors;
};
