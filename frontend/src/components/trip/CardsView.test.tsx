import { canRenderImageTag, canRenderVideoTag } from './CardsView';

describe('CardsView media playback helpers', () => {
  it('allows direct mp4 playback for Instagram previews', () => {
    expect(canRenderVideoTag('http://127.0.0.1:8000/media/clip.mp4', 'instagram')).toBe(true);
  });

  it('does not treat source page links as direct video assets', () => {
    expect(canRenderVideoTag('https://instagram.com/reel/abc', 'instagram')).toBe(false);
  });

  it('allows image previews for downloaded photo posts', () => {
    expect(canRenderImageTag('http://127.0.0.1:8000/media/photo.jpg')).toBe(true);
  });
});
