enum ChannelPlatformType {
  omni,
  x1440;

  static ChannelPlatformType valueOf(String value) {
    switch (value) {
      case 'omni':
        return ChannelPlatformType.omni;
      case 'x1440':
        return ChannelPlatformType.x1440;
      default:
        throw ArgumentError('Unknown value: $value');
    }
  }
}
