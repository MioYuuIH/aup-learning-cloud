# User Guide

This section provides guides for users and administrators of AUP Learning Cloud.

```{toctree}
:maxdepth: 2

admin-manual
```

## For Administrators

- {doc}`admin-manual` - Comprehensive guide for system administrators

## For Users

The user documentation covers:

- Accessing JupyterHub
- Launching notebook environments
- Using different hardware acceleration options (CPU, GPU, NPU)
- Managing your workspace and files
- Best practices for resource usage

## Quick Links

### Common Tasks

- **Login**: Use GitHub OAuth or native credentials
- **Start Server**: Select your desired environment and resources
- **Stop Server**: Always stop your server when finished to free up resources
- **File Management**: Use the file browser in JupyterLab
- **Terminal Access**: Available in all notebook environments

### Resource Selection

When starting your server, you can choose from:

- **Base CPU**: General-purpose computing
- **CV Course**: Computer Vision with GPU acceleration
- **DL Course**: Deep Learning with GPU acceleration
- **LLM Course**: Large Language Model development with GPU acceleration

### Getting Help

For technical support:
1. Check the relevant documentation section
2. Contact your system administrator
3. Report issues on the GitHub repository

## Related Documentation

- [Authentication Guide](../jupyterhub/authentication-guide.md) - Login and authentication
- [JupyterHub Configuration](../jupyterhub/index.md) - System configuration
- [User Management](../jupyterhub/user-management.md) - Account management
