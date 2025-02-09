# Telugu Serial Automation

Automated system for generating and uploading Telugu serial reviews to YouTube.

## Features

- Automatic serial episode scraping
- Video generation with custom thumbnails
- Automatic YouTube uploads
- Scheduled processing
- Error handling and retries
- Token refresh management

## Prerequisites

- Python 3.8 or higher
- FFmpeg installed on the system
- Google Cloud Project with YouTube Data API enabled
- YouTube channel with upload permissions

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/telugu-serial-automation.git
cd telugu-serial-automation
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Set up configuration:
- Copy `config/production.env.example` to `config/production.env`
- Update the values as needed
- Place your `client_secrets.json` in the project root

5. Create required directories:
```bash
mkdir -p data/{audio,video,json} logs tn
```

## YouTube API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing one
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Download client secrets file as `client_secrets.json`
6. Place in project root directory

## Usage

### Running the Service

```bash
# Start the automation service
serial-automation
```

### Configuration

Edit `config/production.env` to customize:
- Video settings
- Scheduling
- File paths
- Logging options

### Adding New Serials

1. Add serial information to `config/serials_config.json`:
```json
{
    "target_serials": {
        "Serial Name": "serial_id"
    }
}
```

2. Add thumbnail image to `tn/` directory:
```
tn/Serial Name.webp
```

## Maintenance

### Log Rotation
- Logs are automatically rotated
- Keeps last 5 log files
- Each file limited to 10MB

### Data Cleanup
- Old files automatically cleaned after 2 days
- Maintains disk space
- Preserves recent data

## Troubleshooting

### Common Issues

1. YouTube Upload Fails
   - Check channel permissions
   - Verify token refresh
   - Check video file integrity

2. Token Refresh Issues
   - Delete `token.pickle`
   - Re-authenticate
   - Check credentials

3. Video Generation Fails
   - Check FFmpeg installation
   - Verify file permissions
   - Check disk space

## License

MIT License - see LICENSE file for details

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request

## Support

For support, please:
1. Check documentation
2. Search existing issues
3. Create new issue if needed 