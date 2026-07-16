'use client';

import { useEffect } from 'react';
import { SquaresBackground as SquaresBackgroundCanvas } from '@/lib/squares-background';

/**
 * Mounts the animated squares canvas on document.body (same behavior as the
 * old squares-bg.js auto-init). Renders nothing itself.
 */
export default function SquaresBackground() {
    useEffect(() => {
        const instance = new SquaresBackgroundCanvas(document.body, {
            direction: 'diagonal',
            speed: 0.3,
            squareSize: 50,
        });
        return () => instance.dispose();
    }, []);

    return null;
}
