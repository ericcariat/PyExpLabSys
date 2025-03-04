def gaussian(x, mu, sigma):
    return np.exp(-np.power(x - mu, 2.)/(2*np.power(sigma, 2.)))

def load_pattern(filename):
    """Load data from a xxxx.pattern file"""
    data = {
        'step_size': None,
        'speed': None,
        'offset': [],
        'error': False
        }
    pattern = []

    f = open(filename, 'r')
    while True:
        line = f.readline()
        if line.startswith('#'):
            # Skip comments
            continue
        if len(line) == 0:
            raise ValueError('Empty line encountered. End FILE with \"<<<END>>>\".')

        # Read data lines
        if line.startswith('<<<DATA>>>'):
            for i in range(2):
                line = f.readline()
                if line.startswith('step_size'):
                    data['step_size'] = float(line.split('=')[1])
                elif line.startswith('speed'):
                    data['speed'] = float(line.split('=')[1])

        # Read pattern
        if line.startswith('<<<PATTERN>>>'):
            while True:
                line = f.readline()
                if line.startswith('<<<END>>>'):
                    z, y = 0, 0
                    for (axis, dist) in pattern:
                        if axis == 'Z':
                            z += dist
                        elif axis == 'Y':
                            y += dist
                    if round(z) != 0 or round(y) != 0:
                        print('Error. Pattern doesn\'t add up to zero ({}, {}).'.format(z, y))
                        data['error'] = True
                    return pattern, data
                elif len(line) == 0:
                    raise ValueError('Empty line encountered during pattern. \
Mark end of FILE/PATTERN with \"<<<END>>>\".')
                elif '-->' in line:
                    newline = line.split('->')[1]
                    data['offset'].append((newline.lstrip(' ')[0], float(newline.split(':')[1])))

                # Repeat pattern
                elif '{' in line:
                    multipattern = []
                    while len(line) > 0:
                        line = f.readline()
                        if '}' in line:
                            multiplier = int(line.split('*')[1])
                            break
                        else:
                            newline = line.lstrip(' ').split(':')
                            multipattern.append((newline[0], float(newline[1])))
                    else:
                        raise ValueError('Multiplier section not finished')
                    for i in range(multiplier):
                        for elements in multipattern:
                            pattern.append(elements)
                else:
                    newline = line.lstrip(' ').split(':')
                    pattern.append((newline[0], float(newline[1])))
            

# Define beam profile
def skewed_gaussian(X, Y, center_big=(-3,-3), center_small=(-3,0),
                    cutoff_big=3, mu=(0,0), sigma=(2,4), A=(3,0.3), radius_aperture=2.25):

    # Low intensity region
    D = (X - center_small[0])**2 + (Y - center_small[1])**2
    Z = gaussian(np.sqrt(D), mu[1], sigma[1])*A[1]
    # High intensity region
    D = (X - center_big[0])**2 + (Y - center_big[1])**2
    index_high = [D <= cutoff_big**2]
    Z[index_high] = gaussian(np.sqrt(D[index_high]), mu[0], sigma[0])*A[0]
    # Aperture mask cutoff
    Z[ X**2 + Y**2 > radius_aperture**2 ] = 0
    return Z

# Integrate beam profile and plot it
def normalize_beam_profile(num=100, moodkwargs=dict()):
    X, dx = np.linspace(-3, 3, num, retstep=True)
    Y, dy = np.linspace(-3, 3, num, retstep=True)
    X, Y = np.meshgrid(X, Y)

    Z = skewed_gaussian(X, Y, **moodkwargs)
    #area = np.sum(Z)*dx*dy
    radius_aperture = moodkwargs['radius_aperture']
    area = np.average(Z[X**2 + Y**2 <= radius_aperture**2])

    fig3 = plt.figure(3)
    bp_ax = fig3.gca(projection='3d')
    bp_ax.plot_wireframe(X, Y, Z/area*10)
    return area, bp_ax


if __name__ == '__main__':

    import sys
    import numpy as np
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    import mpl_toolkits.mplot3d.art3d as art3d
    from matplotlib import cm
    from matplotlib.patches import Circle

    # Radius of aperture
    radius_ap = 2.25 # defining spot size
    # Radius of mask
    r_mask = 2.5 # desired deposition area

    if len(sys.argv) > 0:
        filename = sys.argv[1]
    else:
        filename = 'test_pattern.pattern'

    if len(sys.argv) > 2:
        mood = sys.argv[2]
    else:
        mood = 'bad'

    if mood == 'bad':
        moodkwargs = dict(
            center_big = (-3, -3),
            center_small = (-3,0),
            cutoff_big = 3,
            mu = (0, 0),
            sigma = (2, 4),
            A = (3, 0.3),
            radius_aperture = radius_ap,
            )
    elif mood == 'good':
        moodkwargs = dict(
            center_big = (0,0),
            center_small = (0,0),
            cutoff_big = 0,
            mu = (0, 0),
            sigma = (2, 5),
            A = (0, 1),
            radius_aperture = radius_ap,
            )

    # Import pattern
    pattern, data = load_pattern(filename)

    fig = plt.figure(1)
    projection = fig.gca(projection='3d')

    fig2 = plt.figure(2)
    sketch = fig2.add_subplot(111)


    # Data
    num = 100
    X = np.linspace(-1, 1, num)*10 # mm
    Y = np.linspace(-1, 1, num)*10 # mm
    #dx, dy = dx*10, dy*10
    X, Y = np.meshgrid(X, Y)
    center_mask = (0, 0)

    Z = np.zeros((len(X), len(Y)))

    # Load offset and data
    speed = data['speed'] # mm/s
    z, y = 0, 0
    for (axis, dist) in data['offset']:
        if axis == 'Z':
            z += dist
        elif axis == 'Y':
            y += dist
        else:
            raise NameError('Unknown axis identifier encountered in offset: {}'.format(axis))
    start_point = (z*data['step_size'], y*data['step_size']) # coordinates for start algorithm

    # Insert centers of raster pattern
    #DEPO = [151.9, 75.96]
    #TIME = [5.34, 1.843]
    DEPO = [10.67]
    TIME = [0.5864]
    deposition_rate = sum(DEPO)/sum(TIME) # percent coverage per hour (%/h) relative to 4.5 mm aperture
    spacing_num = 2
    center_list = []
    (z, y) = start_point
    for (axis, dist) in pattern:
        if axis == 'Z':
            z0 = z
            z += dist*data['step_size']
            # Include endpoint on purpose (motor stops briefly)
            centers, step = np.linspace(z0, z, 10*int(abs(z - z0)+1)/spacing_num, retstep=True)
            center_list.append((zip(centers, np.ones(len(centers))*y), abs(step/speed)))
            center_list.append(([(centers[-1], y)], 1.2))
        elif axis == 'Y':
            y0 = y
            y += dist*data['step_size']
            # Include endpoint on purpose (motor stops briefly)
            centers, step = np.linspace(y0, y, 10*int(abs(y - y0)+1)/spacing_num, retstep=True)
            center_list.append((zip(np.ones(len(centers))*z, centers), abs(step/speed)))
            center_list.append(([(z, centers[-1])], 1.2))
        else:
            raise NameError('Unknown axis identifier encountered in pattern: {}'.format(axis))
    #print(center_list)
    print('Chosen pattern is valid.\nStarting simulation...')

    area, bp_ax = normalize_beam_profile(moodkwargs=moodkwargs)

    # Main loop
    total_time = 0
    previous_point = None
    for (coordinates, dt) in center_list:
        for c in coordinates:
            total_time += dt    
            # Sketch raster pattern
            circle = Circle(xy=c, radius=radius_ap, facecolor='b', linewidth=0, alpha=0.05)
            sketch.add_patch(circle)
            if previous_point:
                sketch.plot([previous_point[0], c[0]], [previous_point[1], c[1]], 'ko-', 
                    markersize=4,
                    markerfacecolor='r',
                    markeredgecolor='k',
                    )
            previous_point = c
            Z += skewed_gaussian(X - c[0], Y - c[1], **moodkwargs)/area * deposition_rate * dt/3600.

    print('Time for 1 round: ' + str(total_time) + 's = ' + str(total_time/60.) + 'min')
    circle_mask = Circle(xy=center_mask, radius=r_mask, edgecolor='k', facecolor='none', linewidth=2)
    sketch.add_patch(circle_mask)
    try:
        plt.axis('equal')
    except NotImplementedError:
        pass
    sketch.axis([-10, 10, -10, 10])

    theta = np.linspace(0, 2*np.pi, 100)
    x_mask = r_mask * np.cos(theta)
    y_mask = r_mask * np.sin(theta)
    z_mask = x_mask*0

    tfrac = sum(TIME)/(total_time/3600)
    print(tfrac)
    Z = Z*tfrac
    maximum = np.max(Z)
    average = np.average(Z[ X**2 + Y**2 <= r_mask**2 ])
    print('Average inside dep area (per raster run): {}'.format(average*total_time/3600/sum(TIME)))
    print('Average inside dep area (total): {}'.format(average))
    for i in range(3):
        projection.plot(x_mask, y_mask, z_mask + maximum*float(i)/3, linewidth=2, color='k', alpha=0.6)
    projection.plot(x_mask, y_mask, z_mask + average, linewidth=2, color='k', alpha=0.6)
    projection.set_zlabel('Coverage (\%)')
    #i = [X**2 + Y**2 > r_mask**2]
    #surf = projection.plot_wireframe(X[i], Y[i], Z[i], color='b')
    #surf = projection.scatter(X[i], Y[i], zs=Z[i], c='b', s=5)
    i =  [X**2 + Y**2 <= r_mask**2]
    j1 = np.array([X**2 + Y**2 > r_mask**2])
    j2 = np.array([X**2 + Y**2 < 6**2])
    j = j1[0] == j2[0]
    #surf = projection.scatter(X[i], Y[i], zs=Z[i], c='r', s=15)
    #surf2 = projection.scatter(X[j], Y[j], zs=Z[j], c='b', s=20)
    #surf = projection.plot_wireframe(X[i], Y[i], Z[i], color='r')
    surf3 = projection.plot_surface(X, Y, Z, cmap=cm.hot, vmin=20, vmax=40)
    for ax in [sketch, projection]:
        ax.set_xlabel('x (mm)')
        ax.set_ylabel('y (mm)')
        ax.set_title(filename)
    fig.colorbar(surf3)

    plt.figure()
    plt.contourf(X, Y, Z, [5, 10, 15, 20, 25, 30, 35, 40])
    plt.colorbar()
    if 1:
        step = 10/2
        plt.plot([-step,-step,step,step,-step], [-step,step,step,-step,-step], 'k-', linewidth=2)
    try:
        plt.axis('equal')
    except NotImplementedError:
        pass

    total_intensity = np.sum(Z)
    in_mask_intensity = np.sum(Z[X**2 + Y**2 <= r_mask**2])
    print('Percent of charge within mask: {} %'.format(in_mask_intensity/total_intensity*100))
    plt.show()
