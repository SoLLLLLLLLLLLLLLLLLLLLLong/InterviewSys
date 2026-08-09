/**
 * Background color management with RGB effect support
 */

export type BackgroundMode = 'solid' | 'rgb' | 'transparent';

export interface BackgroundColor {
  r: number;
  g: number;
  b: number;
  a: number;
}

export class LAppBackgroundManager {
  private _currentMode: BackgroundMode = 'solid';
  private _solidColor: BackgroundColor = { r: 0.0, g: 1.0, b: 0.0, a: 1.0 };
  private _rgbSpeed: number = 5;
  private _rgbTime: number = 0;

  /**
   * Set background mode
   */
  public setMode(mode: BackgroundMode): void {
    this._currentMode = mode;
    this._rgbTime = 0; // Reset RGB animation time
  }

  /**
   * Get current background mode
   */
  public getMode(): BackgroundMode {
    return this._currentMode;
  }

  /**
   * Set solid background color from hex string
   */
  public setSolidColorFromHex(hexColor: string): void {
    this._solidColor = this.hexToRgba(hexColor);
  }

  /**
   * Set solid background color from RGBA values
   */
  public setSolidColor(r: number, g: number, b: number, a: number = 1.0): void {
    this._solidColor = { r, g, b, a };
  }

  /**
   * Set RGB effect speed (1-10)
   */
  public setRgbSpeed(speed: number): void {
    this._rgbSpeed = Math.max(1, Math.min(10, speed));
  }

  /**
   * Get current background color based on mode
   * Returns the color that should be applied to gl.clearColor()
   */
  public getCurrentColor(deltaTime: number): BackgroundColor {
    switch (this._currentMode) {
      case 'solid':
        return this._solidColor;

      case 'rgb':
        return this.calculateRgbColor(deltaTime);

      case 'transparent':
        return { r: 0.0, g: 0.0, b: 0.0, a: 0.0 };

      default:
        return this._solidColor;
    }
  }

  /**
   * Calculate RGB effect color based on time
   */
  private calculateRgbColor(deltaTime: number): BackgroundColor {
    // Update RGB animation time
    this._rgbTime += deltaTime * this._rgbSpeed * 0.001;

    // Create smooth RGB cycling using sine waves with phase offsets
    const r = (Math.sin(this._rgbTime) + 1) / 2;
    const g = (Math.sin(this._rgbTime + Math.PI * 2 / 3) + 1) / 2;
    const b = (Math.sin(this._rgbTime + Math.PI * 4 / 3) + 1) / 2;

    return { r, g, b, a: 1.0 };
  }

  /**
   * Convert hex color string to RGBA values (0.0 - 1.0)
   */
  private hexToRgba(hex: string): BackgroundColor {
    // Remove # if present
    hex = hex.replace('#', '');

    // Parse hex values
    const r = parseInt(hex.substring(0, 2), 16) / 255;
    const g = parseInt(hex.substring(2, 4), 16) / 255;
    const b = parseInt(hex.substring(4, 6), 16) / 255;

    return { r, g, b, a: 1.0 };
  }

  /**
   * Reset to default state
   */
  public reset(): void {
    this._currentMode = 'solid';
    this._solidColor = { r: 0.0, g: 1.0, b: 0.0, a: 1.0 };
    this._rgbSpeed = 5;
    this._rgbTime = 0;
  }
}
