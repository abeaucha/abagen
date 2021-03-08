# -*- coding: utf-8 -*-
"""
Structures and functions used for matching samples to atlas
"""

import warnings

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree, distance_matrix

from . import io, transforms


class AtlasTree:
    """
    Representation of a parcellation as a cKDtree for NN lookups

    Parameters
    ----------
    atlas : (N,) niimg-like object or array_like
        Volumetric (niimg-like) or array of parcellation labels. If providing
        an array you must provide `coords` as well
    coords : (N,) array_like, optional
        Coordinates representing points in `atlas`. If provided it is assumed
        that `atlas` is a surface representation (i.e., if `atlas` is
        volumetric simply provide a niimg-like object and the coordinates will
        be derived from the data). Default: None
    atlas_info : {os.PathLike, pandas.DataFrame, None}, optional
        Filepath or dataframe containing information about `atlas`. Must have
        at least columns ['id', 'hemisphere', 'structure'] containing
        information mapping `atlas` IDs to hemisphere (i.e., "L" or "R") and
        broad structural class (i.e.., "cortex", "subcortex/brainstem",
        "cerebellum", "white matter", or "other"). Default: None
    """

    def __init__(self, atlas, coords=None, atlas_info=None):
        from .images import check_img

        try:  # let's first check if it's an image
            atlas = check_img(atlas)
            data, affine = np.asarray(atlas.dataobj), atlas.affine
            nz = data.nonzero()
            if coords is not None:
                warnings.warn('Volumetric image supplied but `coords` is not '
                              'None. Ignoring supplied `coords` and using '
                              'coordinates derived from image.')
            atlas, coords = data[nz], transforms.ijk_to_xyz(np.c_[nz], affine)
            self._volumetric = True
        except TypeError:
            if coords is None:
                raise ValueError('When providing a surface atlas you must '
                                 'also supply relevant geometry `coords`.')
            if len(atlas) != len(coords):
                raise ValueError('Provided `atlas` and `coords` are of '
                                 'differing length.')
            nz = atlas.nonzero()
            atlas, coords = atlas[nz], coords[nz]
            self._volumetric = False

        self._tree = cKDTree(coords)
        self._atlas = np.asarray(atlas)
        self._labels = np.unique(self.atlas).astype(int)
        self._centroids = get_centroids(self.atlas, coords)
        self.atlas_info = atlas_info

    def __repr__(self):
        if self.volumetric:
            suff = f'n_voxel={self.tree.n}'
        else:
            suff = f'n_vertex={self.tree.n}'
        return f'{self.__class__.__name__}[n_rois={len(self.labels)}, {suff}]'

    @property
    def tree(self):
        """ Returns cKDTree constructed from provided atlas and coordinates
        """
        return self._tree

    @property
    def atlas(self):
        """ Returns values of provided atlas
        """
        return self._atlas

    @property
    def volumetric(self):
        """ Return whether `self.atlas` is derived from a volumetric image
        """
        return self._volumetric

    @property
    def labels(self):
        """ Returns unique labels in atlas
        """
        return self._labels

    @property
    def centroids(self):
        """ Return centroids of parcels in `self.atlas`
        """
        return self._centroids

    @property
    def coords(self):
        """ Returns coordinates of underlying cKDTree
        """
        return self.tree.data

    @coords.setter
    def coords(self, pts):
        """ Sets underlying cKDTree to represent provided `pts`
        """
        if len(pts) != len(self.atlas):
            raise ValueError('Provided coordinates do not match length of '
                             'current atlas. Expected {}. Received {}'
                             .format(len(self.atlas), len(pts)))
        if not np.allclose(pts, self.coords):
            self._tree = cKDTree(pts)
            self._centroids = get_centroids(self.atlas, pts)

    @property
    def atlas_info(self):
        """ Returns atlas info dataframe, if it exists
        """
        return self._atlas_info

    @atlas_info.setter
    def atlas_info(self, info):
        """ Sets atlas info dataframe
        """
        from .images import check_atlas_info
        if info is not None:
            self._atlas_info = check_atlas_info(info, self.labels)
        else:
            self._atlas_info = info

    def label_samples(self, annotation, tolerance=2):
        """
        Matches all samples in `annotation` to parcels in `self.atlas`

        Attempts to place each sample provided in `annotation` into a parcel in
        `self.atlas`. If `self.volumetric` is True, this function tries to best
        match samples in `annotation` to parcels in `self.atlas` by:

            1. Determining if the sample falls directly within a parcel,
            2. Checking to see if there are nearby parcels by slowly expanding
               the search space to include nearby voxels, up to a specified
               distance (specified via the `tolerance` parameter),
            3. Assigning the sample to the closest parcel if there are multiple
               nearby parcels, where closest is determined by the parcel
               centroid.

        If at any step a sample can be assigned to a parcel the matching
        process is terminated. If there is still no parcel for a given sample
        after this process the sample is provided a label of 0.

        On the other hand, if `self.volumetric` is False, then samples are
        simply matched to the nearest coordinate in `self.atlas`. Once matched,
        `tolerance` is treated as a standard deviation threshold. That is, all
        samples are matched to the nearest vertex, and then samples whose
        distance to the nearest vertex are more than `tolerance` s.d. above the
        mean distance for all samples are assigned a label of 0.

        Parameters
        ----------
        annotation : (S, 3) array_like
            At a minimum, an array of XYZ coordinates must be provided. If a
            full annotation dataframe is provided, then information from the
            data frame (i.e., on hemisphere + structural assignments of tissue
            samples) is used to constrain matching of regions.
        tolerance : float, optional
            Threshold for assigning samples to parcels. Default: 2

        Returns
        -------
        labels : (S, 1) pandas.DataFrame
            Dataframe with parcel labels for each of `S` samples
        """

        try:
            samples = io.read_annotation(annotation, copy=True)
        except TypeError:
            samples = pd.DataFrame(np.atleast_2d(annotation),
                                   columns=['mni_x', 'mni_y', 'mni_z'])
            if not self.volumetric:
                samples['structure'] = 'cortex'

        if self.volumetric:
            labels = self._match_volume(samples, tolerance)
        else:
            cortex = samples['structure'] == 'cortex'
            labels = np.zeros(len(samples))
            labels[cortex] = self._match_surface(samples[cortex], tolerance)

        return pd.DataFrame(labels, dtype=int,
                            columns=['label'], index=samples.index)

    def _match_surface(self, samples, tolerance):
        """
        Matches samples in `annotation` to labels in surface `self.atlas`

        Assumes atlas is in `fsaverage5` space

        Parameters
        ----------
        samples : (S, 13) pandas.DataFrame
            Annotation information for a given AHBA donor
        tolerance : int, optional
            Threshold for assigning samples to parcels (see Notes). Default: 2

        Returns
        -------
        labels : (S,) np.ndarray
            Parcel labels for all provided `samples`

        Notes
        -----
        All samples are matched to the nearest vertex, and then samples whose
        distance to the nearest vertex are more than `tolerance` s.d. above
        the mean distance computed across all matched samples are unassigned.
        """

        dist, idx = self.tree.query(samples[['mni_x', 'mni_y', 'mni_z']], k=1)
        labels = self.atlas[idx]

        if self.atlas_info is not None:
            labels = _check_label(labels, samples, self.atlas_info)

        if len(labels) > 1:
            with np.errstate(invalid='ignore'):
                mask = dist > dist.mean() + (dist.std(ddof=1) * tolerance)
            labels[mask] = 0

        return labels

    def _match_volume(self, samples, tolerance):
        """
        Matches samples in `annotation` to labels in volumetric `self.atlas`

        Parameters
        ----------
        samples : (S, 13) pandas.DataFrame
            Annotation information for a given AHBA donor
        tolerance : int, optional
            Threshold for assigning samples to parcels (see Notes). Default: 2

        Returns
        ------
        labels : (S,) np.ndarray
            Parcel labels for all provided `samples`

        Notes
        -----
        The provided `threshold` is used as a mm cutoff; that is, samples that
        do not fall w/i a `tolerance` mm radius of any parcel are not assigned.
        """

        cols = ['mni_x', 'mni_y', 'mni_z']
        tol = 0
        labels = np.zeros(len(samples))
        idx = np.ones(len(samples), dtype=bool)
        while tol <= tolerance and np.sum(idx) > 0:
            subsamp = samples.loc[idx]
            matches = self.tree.query_ball_point(subsamp[cols], tol)
            labs = np.zeros(len(subsamp))
            for n, match in enumerate(matches):
                if len(match) > 0:
                    labs[n] = self._assign_sample(self.atlas[match],
                                                  subsamp.iloc[[n]])
            labels[idx] = labs
            idx = labels == 0
            tol += 1

        return labels

    def _assign_sample(self, possible, sample):
        """
        Determines which parcel `sample` belongs to amongst `possible` labels

        Parameters
        ----------
        possible : list-of-int
            Potential labels for `sample`
        sample_info : pandas.DataFrame
            A single row of an `annotation` file

        Returns
        -------
        label : int
            Chosen label of `sample`
        """

        labels, counts = np.unique(possible, return_counts=True)

        # if atlas_info and sample_info are provided, drop potential labels who
        # don't match hemisphere or structural class defined in `sample_info`
        if self.atlas_info is not None:
            possible = _check_label(labels, sample, self.atlas_info)
            labels, counts = np.unique(possible[possible.nonzero()],
                                       return_counts=True)

        # if all the labels are now zero, c'est la vie
        if labels.size == 0:
            return 0

        # if there is only one ROI in the vicinity, use that
        elif labels.size == 1:
            return labels[0]

        # if more than one ROI in the vicinity, return the most frequent
        indmax, = np.where(counts == counts.max())
        if indmax.size == 1:
            return labels[indmax[0]]

        # if two or more parcels tied for neighboring frequency, use ROI
        # with closest centroid to `coords`
        coords = sample[['mni_x', 'mni_y', 'mni_z']]
        centroids = np.row_stack([self.centroids[lab] for lab in labels])
        return labels[closest_centroid(coords, centroids)]


def _check_label(label, sample_info, atlas_info):
    """
    Checks that `label` defined by `sample_info` is coherent with `atlas_info`

    Non-matching labels are re-assigned a value of 0

    Parameters
    ----------
    label : int or array_like
        Tenative label(s) for sample(s) described by `sample_info`
    sample_info : pandas.Series or pandas.DataFrame
        Row(s) of an `annotation` file, corresponding to the given `label`
    atlas_info : pandas.DataFrame
        Dataframe containing information about the atlas of interest. Must have
        at least columns ['id', 'hemisphere', 'structure'] containing
        information mapping atlas IDs to hemisphere and broad structural class

    Returns
    -------
    label : np.ndarray
        New label(s) for sample(s)
    """

    cols = ['hemisphere', 'structure']
    label = np.atleast_1d(label)

    if len(sample_info) != len(label):
        sample_info = pd.concat([sample_info] * len(label))

    try:
        ai = atlas_info.loc[label, cols]
        drop = np.zeros_like(label, dtype=bool)
        # only compare structure for bilateral ROIs
        mask = np.asarray(ai['hemisphere'] == "B")
        drop[mask] = (np.asarray(atlas_info.loc[ai[mask].index, 'structure'])
                      != np.asarray(sample_info.loc[mask, 'structure']))
        # but compare hemisphere + structure for L/R ROIs
        mask = np.logical_not(mask)
        drop[mask] = np.any(np.asarray(atlas_info.loc[ai[mask].index, cols])
                            != np.asarray(sample_info.loc[mask, cols]), axis=1)
        label[drop] = 0
    except KeyError:
        pass

    return label


def get_centroids(data, coordinates, labels=None):
    """
    Finds centroids of `data` in `coordinates` space

    Parameters
    ----------
    data : (N,) array_like
        Data labelling all `N` points in `coordinates`
    coordinates : (N, D) array_like
        Coordinates of `data` array
    labels : array_like, optional
        List of values containing labels of which to find centroids. Default:
        all possible labels in `data`

    Returns
    -------
    centroids : dict
        Where keys are labels and values are centroids
    """

    data, coordinates = np.asarray(data), np.atleast_2d(coordinates)

    if labels is None:
        labels = np.trim_zeros(np.unique(data))

    centroids = np.zeros((len(labels), coordinates.shape[-1]))
    for n, lab in enumerate(labels):
        centroids[n] = coordinates[data == lab].mean(axis=0)

    return dict(zip(labels, centroids))


def closest_centroid(coords, centroids, return_dist=False):
    """
    Returns index of `centroids` closest to `coords` (Euclidean distance)

    Parameters
    ----------
    coord : (S, 3) array_like
        Coordinates of samples
    centroids : (N, 3) array_like
        Centroids of parcels
    return_dist : bool, optional
        Whether to also return distance of closest centroid

    Returns
    -------
    closest : (S,) np.ndarray
        Indices of closest centroid in `centroids` to `coords`
    distance : (S,) np.ndarray
        Distances of closest centroid in `centroids` to `coords`. Only returned
        if `return_dist=True`
    """

    coords, centroids = np.atleast_2d(coords), np.atleast_2d(centroids)
    distances = distance_matrix(coords, centroids)
    closest = distances.argmin(axis=1)

    if return_dist:
        return closest, distances[range(len(closest)), closest]

    return closest