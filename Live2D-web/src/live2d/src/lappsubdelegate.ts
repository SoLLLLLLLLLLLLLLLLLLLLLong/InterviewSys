/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import * as LAppDefine from './lappdefine';
import { LAppGlManager } from './lappglmanager';
import { LAppLive2DManager } from './lapplive2dmanager';
import { LAppPal } from './lapppal';
import { LAppTextureManager } from './lapptexturemanager';
import { LAppView } from './lappview';
import { LAppBackgroundManager, BackgroundMode } from './lappbackgroundmanager';
import { CubismMatrix44 } from '../Framework/src/math/cubismmatrix44';

/**
 * Canvasに関連する操作を取りまとめるクラス
 */
export class LAppSubdelegate {
  /**
   * コンストラクタ
   */
  public constructor() {
    this._canvas = null;
    this._glManager = new LAppGlManager();
    this._textureManager = new LAppTextureManager();
    this._live2dManager = new LAppLive2DManager();
    this._view = new LAppView();
    this._frameBuffer = null;
    this._captured = false;
    this._backgroundManager = new LAppBackgroundManager();
    this._lastFrameTime = Date.now();
    this._modelPositionX = 0.0;
    this._modelPositionY = 0.0;
    this._modelScale = 1.0;
  }

  /**
   * デストラクタ相当の処理
   */
  public release(): void {
    this._resizeObserver.unobserve(this._canvas);
    this._resizeObserver.disconnect();
    this._resizeObserver = null;

    this._live2dManager.release();
    this._live2dManager = null;

    this._view.release();
    this._view = null;

    this._textureManager.release();
    this._textureManager = null;

    this._glManager.release();
    this._glManager = null;
  }

  /**
   * APPに必要な物を初期化する。
   */
  public initialize(canvas: HTMLCanvasElement): boolean {
    if (!this._glManager.initialize(canvas)) {
      return false;
    }

    this._canvas = canvas;

    if (LAppDefine.CanvasSize === 'auto') {
      this.resizeCanvas();
    } else {
      canvas.width = LAppDefine.CanvasSize.width;
      canvas.height = LAppDefine.CanvasSize.height;
    }

    this._textureManager.setGlManager(this._glManager);

    const gl = this._glManager.getGl();

    if (!this._frameBuffer) {
      this._frameBuffer = gl.getParameter(gl.FRAMEBUFFER_BINDING);
    }

    // 透過設定
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // AppViewの初期化
    this._view.initialize(this);
    this._view.initializeSprite();

    this._live2dManager.initialize(this);

    this._resizeObserver = new ResizeObserver(
      (entries: ResizeObserverEntry[], observer: ResizeObserver) =>
        this.resizeObserverCallback.call(this, entries, observer)
    );
    this._resizeObserver.observe(this._canvas);

    return true;
  }

  /**
   * Resize canvas and re-initialize view.
   */
  public onResize(): void {
    this.resizeCanvas();
    this._view.initialize(this);
    this._view.initializeSprite();
  }

  private resizeObserverCallback(
    entries: ResizeObserverEntry[],
    observer: ResizeObserver
  ): void {
    if (LAppDefine.CanvasSize === 'auto') {
      this._needResize = true;
    }
  }

  /**
   * ループ処理
   */
  public update(): void {
    if (this._glManager.getGl().isContextLost()) {
      return;
    }

    // キャンバスのサイズが変わっている場合はリサイズに必要な処理をする。
    if (this._needResize) {
      this.onResize();
      this._needResize = false;
    }

    const gl = this._glManager.getGl();

    // Calculate deltaTime for animations
    const currentTime = Date.now();
    const deltaTime = currentTime - this._lastFrameTime;
    this._lastFrameTime = currentTime;

    // Get dynamic background color from background manager
    const bgColor = this._backgroundManager.getCurrentColor(deltaTime);

    // 画面の初期化 with dynamic background color
    gl.clearColor(bgColor.r, bgColor.g, bgColor.b, bgColor.a);

    // 深度テストを有効化
    gl.enable(gl.DEPTH_TEST);

    // 近くにある物体は、遠くにある物体を覆い隠す
    gl.depthFunc(gl.LEQUAL);

    // カラーバッファや深度バッファをクリアする
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.clearDepth(1.0);

    // 透過設定
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    // 描画更新
    this._view.render();
  }

  /**
   * シェーダーを登録する。
   */
  public createShader(): WebGLProgram {
    const gl = this._glManager.getGl();

    // バーテックスシェーダーのコンパイル
    const vertexShaderId = gl.createShader(gl.VERTEX_SHADER);

    if (vertexShaderId == null) {
      LAppPal.printMessage('failed to create vertexShader');
      return null;
    }

    const vertexShader: string =
      'precision mediump float;' +
      'attribute vec3 position;' +
      'attribute vec2 uv;' +
      'varying vec2 vuv;' +
      'void main(void)' +
      '{' +
      '   gl_Position = vec4(position, 1.0);' +
      '   vuv = uv;' +
      '}';

    gl.shaderSource(vertexShaderId, vertexShader);
    gl.compileShader(vertexShaderId);

    // フラグメントシェーダのコンパイル
    const fragmentShaderId = gl.createShader(gl.FRAGMENT_SHADER);

    if (fragmentShaderId == null) {
      LAppPal.printMessage('failed to create fragmentShader');
      return null;
    }

    const fragmentShader: string =
      'precision mediump float;' +
      'varying vec2 vuv;' +
      'uniform sampler2D texture;' +
      'void main(void)' +
      '{' +
      '   gl_FragColor = texture2D(texture, vuv);' +
      '}';

    gl.shaderSource(fragmentShaderId, fragmentShader);
    gl.compileShader(fragmentShaderId);

    // プログラムオブジェクトの作成
    const programId = gl.createProgram();
    gl.attachShader(programId, vertexShaderId);
    gl.attachShader(programId, fragmentShaderId);

    gl.deleteShader(vertexShaderId);
    gl.deleteShader(fragmentShaderId);

    // リンク
    gl.linkProgram(programId);
    gl.useProgram(programId);

    return programId;
  }

  public getTextureManager(): LAppTextureManager {
    return this._textureManager;
  }

  public getFrameBuffer(): WebGLFramebuffer {
    return this._frameBuffer;
  }

  public getCanvas(): HTMLCanvasElement {
    return this._canvas;
  }

  public getGlManager(): LAppGlManager {
    return this._glManager;
  }

  public getLive2DManager(): LAppLive2DManager {
    return this._live2dManager;
  }

  /**
   * Get background manager instance
   */
  public getBackgroundManager(): LAppBackgroundManager {
    return this._backgroundManager;
  }

  /**
   * Set background mode (solid, rgb, transparent)
   */
  public setBackgroundMode(mode: BackgroundMode): void {
    this._backgroundManager.setMode(mode);
  }

  /**
   * Set solid background color from hex string
   */
  public setBackgroundColor(hexColor: string): void {
    this._backgroundManager.setSolidColorFromHex(hexColor);
  }

  /**
   * Set RGB effect speed (1-10)
   */
  public setRgbSpeed(speed: number): void {
    this._backgroundManager.setRgbSpeed(speed);
  }

  /**
   * Set model position (X, Y coordinates)
   */
  public setModelPosition(x: number, y: number): void {
    this._modelPositionX = x;
    this._modelPositionY = y;
    this.applyModelTransform();
  }

  /**
   * Set model scale
   */
  public setModelScale(scale: number): void {
    this._modelScale = scale;
    this.applyModelTransform();
  }

  /**
   * Get available expression names for the current model
   */
  public getExpressionNames(): string[] {
    const model = this._live2dManager._models.at(0);
    if (!model) return [];

    const expressions = model._expressions;
    const names: string[] = [];

    for (let i = 0; i < expressions.getSize(); i++) {
      names.push(expressions._keyValues[i].first);
    }

    return names;
  }

  /**
   * Set expression by name
   */
  public setExpression(expressionName: string): void {
    const model = this._live2dManager._models.at(0);
    if (model) {
      model.setExpression(expressionName);
    }
  }

  /**
   * Set random expression
   */
  public setRandomExpression(): void {
    const model = this._live2dManager._models.at(0);
    if (model) {
      model.setRandomExpression();
    }
  }

  /**
   * Play audio and trigger lip sync
   */
  public playAudioWithLipSync(audioPath: string = '/audio/sample.wav'): void {
    const model = this._live2dManager._models.at(0);
    if (model) {
      console.log('🎯 [LipSync] Starting audio playback from settings');
      console.log(`🎵 [LipSync] Loading audio file: ${audioPath}`);

      // Initialize the GenericAudioFileHandler for lip sync
      model._genericAudioFileHandler.start(audioPath);

      console.log('✅ [LipSync] GenericAudioFileHandler.start() called');
    }
  }

  /**
   * Apply model transformations (position and scale)
   */
  private applyModelTransform(): void {
    const model = this._live2dManager._models.at(0);
    if (model) {
      const matrix = model.getModelMatrix();
      matrix.loadIdentity();
      matrix.translateX(this._modelPositionX);
      matrix.translateY(this._modelPositionY);
      matrix.scale(this._modelScale, this._modelScale);
    }
  }

  /**
   * Change the model by index
   */
  public changeModel(modelIndex: number): void {
    this._live2dManager.changeScene(modelIndex);
  }

  /**
   * Resize the canvas to fill the screen.
   */
  private resizeCanvas(): void {
    this._canvas.width = this._canvas.clientWidth * window.devicePixelRatio;
    this._canvas.height = this._canvas.clientHeight * window.devicePixelRatio;

    const gl = this._glManager.getGl();

    gl.viewport(0, 0, gl.drawingBufferWidth, gl.drawingBufferHeight);
  }

  /**
   * マウスダウン、タッチダウンしたときに呼ばれる。
   */
  public onPointBegan(pageX: number, pageY: number): void {
    if (!this._view) {
      LAppPal.printMessage('view notfound');
      return;
    }
    this._captured = true;

    const localX: number = pageX - this._canvas.offsetLeft;
    const localY: number = pageY - this._canvas.offsetTop;

    this._view.onTouchesBegan(localX, localY);
  }

  /**
   * マウスポインタが動いたら呼ばれる。
   */
  public onPointMoved(pageX: number, pageY: number): void {
    if (!this._captured) {
      return;
    }

    const localX: number = pageX - this._canvas.offsetLeft;
    const localY: number = pageY - this._canvas.offsetTop;

    this._view.onTouchesMoved(localX, localY);
  }

  /**
   * クリックが終了したら呼ばれる。
   */
  public onPointEnded(pageX: number, pageY: number): void {
    this._captured = false;

    if (!this._view) {
      LAppPal.printMessage('view notfound');
      return;
    }

    const localX: number = pageX - this._canvas.offsetLeft;
    const localY: number = pageY - this._canvas.offsetTop;

    this._view.onTouchesEnded(localX, localY);
  }

  /**
   * タッチがキャンセルされると呼ばれる。
   */
  public onTouchCancel(pageX: number, pageY: number): void {
    this._captured = false;

    if (!this._view) {
      LAppPal.printMessage('view notfound');
      return;
    }

    const localX: number = pageX - this._canvas.offsetLeft;
    const localY: number = pageY - this._canvas.offsetTop;

    this._view.onTouchesEnded(localX, localY);
  }

  public isContextLost(): boolean {
    return this._glManager.getGl().isContextLost();
  }

  /**
   * Get available motion group names from the loaded model
   */
  public getMotionGroupNames(): string[] {
    const model = this._live2dManager._models?.at(0);
    if (!model || !model._modelSetting) {
      return [];
    }

    const groups: string[] = [];
    const groupCount = model._modelSetting.getMotionGroupCount();

    for (let i = 0; i < groupCount; i++) {
      const groupName = model._modelSetting.getMotionGroupName(i);
      groups.push(groupName);
    }

    return groups;
  }

  /**
   * Get all available motions with their file names
   */
  public getAllMotions(): Array<{ group: string; index: number; name: string }> {
    const model = this._live2dManager._models?.at(0);
    if (!model || !model._modelSetting) {
      return [];
    }

    const motions: Array<{ group: string; index: number; name: string }> = [];
    const groupCount = model._modelSetting.getMotionGroupCount();

    for (let i = 0; i < groupCount; i++) {
      const groupName = model._modelSetting.getMotionGroupName(i);
      const motionCount = model._modelSetting.getMotionCount(groupName);

      for (let j = 0; j < motionCount; j++) {
        const motionFileName = model._modelSetting.getMotionFileName(groupName, j);
        // Extract just the filename without path and extension
        const displayName = motionFileName
          .split('/').pop()
          ?.replace('.motion3.json', '') || `${groupName}_${j}`;
        
        motions.push({
          group: groupName,
          index: j,
          name: `[${groupName}] ${displayName}`
        });
      }
    }

    return motions;
  }

  private _canvas: HTMLCanvasElement;

  /**
   * View情報
   */
  private _view: LAppView;

  /**
   * テクスチャマネージャー
   */
  private _textureManager: LAppTextureManager;
  private _frameBuffer: WebGLFramebuffer;
  private _glManager: LAppGlManager;
  private _live2dManager: LAppLive2DManager;

  /**
   * ResizeObserver
   */
  private _resizeObserver: ResizeObserver;

  /**
   * クリックしているか
   */
  private _captured: boolean;

  private _needResize: boolean;

  /**
   * Background manager for dynamic color control
   */
  private _backgroundManager: LAppBackgroundManager;

  /**
   * Last frame timestamp for deltaTime calculation
   */
  private _lastFrameTime: number;

  /**
   * Model position and scale
   */
  private _modelPositionX: number;
  private _modelPositionY: number;
  private _modelScale: number;
}
