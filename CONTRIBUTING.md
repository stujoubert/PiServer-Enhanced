# Contributing to PiServer

Thank you for your interest in contributing to PiServer! 🎉

## 🤝 How to Contribute

### Reporting Bugs

If you find a bug:
1. Check if it's already reported in [Issues](https://github.com/stujoubert/PiServer/issues)
2. If not, create a new issue with:
   - Clear title
   - Steps to reproduce
   - Expected vs actual behavior
   - Your environment (OS, Python version, etc.)
   - Error messages/logs

### Suggesting Features

Have an idea? We'd love to hear it!
1. Check existing [Issues](https://github.com/stujoubert/PiServer/issues) first
2. Create a new issue with:
   - Clear description of the feature
   - Use cases
   - Potential implementation ideas

### Pull Requests

1. **Fork the repository**
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Test thoroughly**
5. **Commit**: Use clear commit messages
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation
   - `style:` for formatting
   - `refactor:` for code restructuring
   - `test:` for adding tests
6. **Push**: `git push origin feature/your-feature-name`
7. **Open a Pull Request**

### Code Style

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add comments for complex logic
- Keep functions small and focused
- Write docstrings for functions

### Testing

Before submitting:
- Test on your local environment
- Verify existing features still work
- Add tests for new features (if applicable)

## 📋 Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/PiServer.git
cd PiServer

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run in development mode
export ATT_ENV=dev
export ATT_DB=/tmp/test.db
python server.py
```

## 🎯 Priority Areas

We especially welcome contributions in:
- Mobile app development
- Advanced analytics/reporting
- Integration with other systems
- UI/UX improvements
- Performance optimizations
- Documentation improvements
- Translation to other languages

## 📞 Questions?

- Open an issue for questions
- Check existing documentation
- Join our community discussions

Thank you for contributing! 🙏
