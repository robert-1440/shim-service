enum PlatformChannelType {
  omni,
  x1440;

  static PlatformChannelType valueOf(String value) {
    switch (value) {
      case 'omni':
        return PlatformChannelType.omni;
      case 'x1440':
        return PlatformChannelType.x1440;
      default:
        throw ArgumentError.value(value, 'value', 'Invalid value');
    }
  }
}