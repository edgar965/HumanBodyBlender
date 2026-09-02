# SPDX-License-Identifier: GPL-3.0-or-later
#
# Image analysis utilities for the HumanBody Asset Creator.
# Pure numpy module — no bpy operators, only data transforms.

import numpy as np


class Bildanalyse:
    u"""Die frueheren Modulfunktionen, gebuendelt."""

    @staticmethod
    def load_image_pixels(bpy_image):
        """Load a Blender image into a numpy array (H, W, 4) float32, top-down.

        Blender stores pixels bottom-up in a flat RGBA list.  We reshape and
        flip vertically so row 0 is the top of the image.
        """
        w, h = bpy_image.size
        pixels = np.array(bpy_image.pixels[:], dtype=np.float32).reshape(h, w, 4)
        # Flip vertically: Blender is bottom-up, we want top-down
        return pixels[::-1].copy()

    @staticmethod
    def classify_foreground(pixels, mode, threshold):
        """Return a boolean mask (H, W) marking foreground pixels.

        *mode* is one of ``'ALPHA'``, ``'DARK'``, ``'LIGHT'``.
        """
        if mode == 'ALPHA':
            return pixels[:, :, 3] >= threshold
        brightness = 0.299 * pixels[:, :, 0] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 2]
        if mode == 'DARK':
            # Foreground is bright on dark background
            return brightness >= threshold
        # LIGHT — foreground is dark on light background
        return brightness <= threshold

    @staticmethod
    def compute_body_bounds(vertices_xz):
        """Compute bounding box of vertex (x, z) positions.

        Parameters
        ----------
        vertices_xz : ndarray (N, 2)
            Column 0 = x, column 1 = z.

        Returns
        -------
        tuple (x_min, x_max, z_min, z_max)

        BEWUSST EIN TUPEL (01.09.2026): Eine Achsenschachtel mit vier
        Zahlen ist kein Datensatz mit vier Bedeutungen, und der einzige
        Aufrufer (`auto_fit_scale`) packt sie in seiner ersten Zeile
        wieder aus. Ein eigener Halter waere hier mehr Bauwerk als
        Nutzen — anders als bei `Bildabbildung` nebenan, die sieben
        Felder ueber mehrere Methoden traegt.
        """
        return (
            float(vertices_xz[:, 0].min()),
            float(vertices_xz[:, 0].max()),
            float(vertices_xz[:, 1].min()),
            float(vertices_xz[:, 1].max()),
        )

    @staticmethod
    def auto_fit_scale(body_bounds, fg_mask):
        """Compute scale and offset to map the foreground mask onto body bounds.

        The vertical extent of the foreground (non-zero rows) is matched to the
        body Z range.  Horizontally the foreground is centred on the body midpoint.

        Returns
        -------
        tuple (scale_x, scale_z, offset_x, offset_z)
            Mapping:  image_col = (vertex_x - offset_x) * scale_x
                      image_row = (vertex_z_top - vertex_z) * scale_z
            (top-down row ordering)

        BEWUSST EIN TUPEL: Die vier Werte gehen in derselben Zeile in
        `Bildabbildung` — dort haben sie Namen und werden weitergereicht.
        Ein zweiter Halter dazwischen brächte nichts.
        """
        x_min, x_max, z_min, z_max = body_bounds
        h, w = fg_mask.shape

        # Foreground row/col extents
        rows = np.any(fg_mask, axis=1)
        cols = np.any(fg_mask, axis=0)
        if not rows.any():
            return 1.0, 1.0, 0.0, 0.0

        row_indices = np.where(rows)[0]
        col_indices = np.where(cols)[0]
        fg_row_min, fg_row_max = row_indices[0], row_indices[-1]
        fg_col_min, fg_col_max = col_indices[0], col_indices[-1]

        fg_height = max(fg_row_max - fg_row_min, 1)
        fg_width = max(fg_col_max - fg_col_min, 1)

        body_z_range = max(z_max - z_min, 1e-6)
        body_x_range = max(x_max - x_min, 1e-6)

        # Scale: pixels per meter
        scale_z = fg_height / body_z_range
        scale_x = fg_width / body_x_range

        # Offsets: map body centre to foreground centre
        fg_col_center = (fg_col_min + fg_col_max) / 2.0
        body_x_center = (x_min + x_max) / 2.0
        offset_x = body_x_center - fg_col_center / scale_x

        offset_z = z_max - fg_row_min / scale_z  # top-down: z_max → row_min

        return float(scale_x), float(scale_z), float(offset_x), float(offset_z)

    @staticmethod
    def vertex_to_image_uv(vertices_xz, sx, sz, ox, oz, w, h):
        """Project vertex (x, z) positions to image (col, row) coordinates.

        Parameters
        ----------
        vertices_xz : ndarray (N, 2)
        sx, sz, ox, oz : float  — scale / offset from *auto_fit_scale*
        w, h : int  — image dimensions

        Returns
        -------
        ndarray (N, 2) of (col, row), float32, NOT clipped.
        """
        col = (vertices_xz[:, 0] - ox) * sx
        row = (oz - vertices_xz[:, 1]) * sz  # top-down
        return np.column_stack([col, row]).astype(np.float32)

    @staticmethod
    def classify_garment_faces(face_centers_xz, face_uv, mask, w, h):
        """Determine which faces are covered by the garment foreground.

        Parameters
        ----------
        face_centers_xz : ndarray (F, 2) — NOT used directly, kept for API compat
        face_uv : ndarray (F, 2) of (col, row) from *vertex_to_image_uv*
        mask : ndarray (H, W) bool — foreground mask
        w, h : int

        Returns
        -------
        ndarray (F,) bool
        """
        col = np.clip(np.round(face_uv[:, 0]).astype(int), 0, w - 1)
        row = np.clip(np.round(face_uv[:, 1]).astype(int), 0, h - 1)
        return mask[row, col]

    @staticmethod
    def compute_offset_profile(body_xz, mask, sx, sz, ox, oz, w, h,
                               num_scanlines=64):
        """Compute a normalised offset profile along the Z axis.

        For each of *num_scanlines* horizontal scan lines we measure how much
        wider the garment silhouette is compared to the body silhouette.  The
        result is normalised to 0..1.

        Returns
        -------
        z_values : ndarray (S,)
        weights  : ndarray (S,) in [0, 1]
        """
        rows_fg = np.any(mask, axis=1)
        if not rows_fg.any():
            return np.zeros(1), np.zeros(1)

        row_indices = np.where(rows_fg)[0]
        row_min, row_max = row_indices[0], row_indices[-1]

        scan_rows = np.linspace(row_min, row_max, num_scanlines).astype(int)
        scan_rows = np.clip(scan_rows, 0, h - 1)

        z_values = oz - scan_rows.astype(np.float32) / sz

        # Body x-extent per scanline
        body_z_mask = np.abs(body_xz[:, 1][:, None] - z_values[None, :]) < (0.5 / sz)
        # shape (N_verts, S)

        weights = np.zeros(num_scanlines, dtype=np.float32)

        for i, row in enumerate(scan_rows):
            # Garment width at this scanline
            fg_cols = np.where(mask[row])[0]
            if len(fg_cols) == 0:
                continue
            garment_width = (fg_cols[-1] - fg_cols[0]) / max(sx, 1e-6)

            # Body width at this Z height
            verts_at_z = body_xz[body_z_mask[:, i]]
            if len(verts_at_z) == 0:
                continue
            body_width = verts_at_z[:, 0].max() - verts_at_z[:, 0].min()
            if body_width < 1e-6:
                continue

            ratio = (garment_width - body_width) / body_width
            weights[i] = max(0.0, min(1.0, ratio))

        # Normalise to 0..1 range
        wmax = weights.max()
        if wmax > 1e-6:
            weights /= wmax

        return z_values, weights

    @staticmethod
    def interpolate_vertex_weights(vertices_z, z_values, weights):
        """Interpolate offset weights for each vertex based on its Z position.

        Returns
        -------
        ndarray (N,) float32 in [0, 1]
        """
        return np.clip(
            np.interp(vertices_z, z_values[::-1], weights[::-1]),
            0.0, 1.0
        ).astype(np.float32)
