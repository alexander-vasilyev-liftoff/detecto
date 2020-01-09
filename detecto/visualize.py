import cv2
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import torch

from detecto.utils import reverse_normalize, normalize_transform
from torchvision import transforms


def detect_video(model, input_file, output_file, fps=30):
    """Takes in a video and produces an output video with object detection
    run on it (i.e. displays boxes around detected objects in real-time).
    Output videos should have the .avi file extension. Note: some apps,
    such as macOS's QuickTime Player, have difficulty viewing these
    output videos. It's recommended that you download and use
    `VLC <https://www.videolan.org/vlc/index.html>`_ if this occurs.


    :param model: The trained model with which to run object detection.
    :type model: detecto.core.Model
    :param input_file: The path to the input video.
    :type input_file: str
    :param output_file: The name of the output file. Should have a .avi
        file extension.
    :type output_file: str
    :param fps: (Optional) Frames per second of the output video.
        Defaults to 30.
    :type fps: int

    **Example**::

        >>> from detecto.core import Model
        >>> from detecto.visualize import detect_video

        >>> model = Model.load('model_weights.pth', ['tick', 'gate'])
        >>> detect_video(model, 'input_vid.mp4', 'output_vid.avi', fps=20)
    """

    # Read in the video
    video = cv2.VideoCapture(input_file)

    # Video frame dimensions
    frame_width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Scale down frames when passing into model for faster speeds
    scaled_size = 800
    scale_down_factor = min(frame_height, frame_width) / scaled_size

    # The VideoWriter with which we'll write our video with the boxes and labels
    # Parameters: filename, fourcc, fps, frame_size
    out = cv2.VideoWriter(output_file, cv2.VideoWriter_fourcc(*'DIVX'), fps, (frame_width, frame_height))

    # Transform to apply on individual frames of the video
    transform_frame = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize(scaled_size),
        transforms.ToTensor(),
        normalize_transform(),
    ])

    # Loop through every frame of the video
    while True:
        ret, frame = video.read()
        # Stop the loop when we're done with the video
        if not ret:
            break

        # The transformed frame is what we'll feed into our model
        transformed_frame = transform_frame(frame)
        predictions = model.predict_top(transformed_frame)

        # Add the top prediction of each class to the frame
        for label, box, score in zip(*predictions):
            # Since the predictions are for scaled down frames,
            # we need to increase the box dimensions
            box *= scale_down_factor

            # Create the box around each object detected
            # Parameters: frame, (start_x, start_y), (end_x, end_y), (r, g, b), thickness
            cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (255, 0, 0), 3)

            # Write the label and score for the boxes
            # Parameters: frame, text, (start_x, start_y), font, font scale, (r, g, b), thickness
            cv2.putText(frame, '{}: {}'.format(label, round(score.item(), 2)), (box[0], box[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 3)

        # Write this frame to our video file
        out.write(frame)

        # If the 'q' key is pressed, break from the loop
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break

    # When finished, release the video capture and writer objects
    video.release()
    out.release()

    # Close all the frames
    cv2.destroyAllWindows()


def plot_prediction_grid(model, images, dim=None, figsize=None):
    """Plots a grid of images with boxes drawn around predicted objects.

    :param model: The trained model with which to run object detection.
    :type model: detecto.core.Model
    :param images: An iterable of images to plot. If the images are
        normalized torch.Tensor images, they will automatically be
        reverse-normalized and converted to PIL images for plotting.
    :type images: iterable
    :param dim: (Optional) The dimensions of the grid in the format
        ``(rows, cols)``. If no value is given, the grid is of the shape
        ``(len(images), 1)``. ``rows * cols`` must match the number of
        given images, or a ValueError is raised. Defaults to None.
    :type dim: tuple or None
    :param figsize: (Optional) The size of the entire grid in the format
        ``(width, height)``. Defaults to None.
    :type figsize: tuple or None

    **Example**::

        >>> from detecto.core import Model
        >>> from detecto.utils import read_image
        >>> from detecto.visualize import plot_prediction_grid

        >>> model = Model.load('model_weights.pth', ['tick', 'gate'])
        >>> images = []
        >>> for i in range(4):
        >>>     image = read_image('image{}.jpg'.format(i))
        >>>     images.append(image)
        >>> plot_prediction_grid(model, images, dim=(2, 2), figsize=(8, 8))
    """

    # If not specified, show all in one column
    if dim is None:
        dim = (len(images), 1)

    if dim[0] * dim[1] != len(images):
        raise ValueError('Grid dimensions do not match size of list of images')

    fig, axes = plt.subplots(dim[0], dim[1], figsize=figsize)

    # Loop through each image and position in the grid
    index = 0
    for i in range(dim[0]):
        for j in range(dim[1]):
            image = images[index]
            preds = model.predict_top(image)

            # If already a tensor, reverse normalize it and turn it back
            if isinstance(image, torch.Tensor):
                image = transforms.ToPILImage()(reverse_normalize(image))
            index += 1

            # Get the correct axis
            if dim[0] <= 1 and dim[1] <= 1:
                ax = axes
            elif dim[0] <= 1:
                ax = axes[j]
            elif dim[1] <= 1:
                ax = axes[i]
            else:
                ax = axes[i, j]

            ax.imshow(image)

            # Plot boxes and labels
            for label, box, score in zip(*preds):
                width, height = box[2] - box[0], box[3] - box[1]
                initial_pos = (box[0], box[1])
                rect = patches.Rectangle(initial_pos, width, height, linewidth=1,
                                         edgecolor='r', facecolor='none')
                ax.add_patch(rect)

                ax.text(box[0] + 5, box[1] - 10, '{}: {}'
                        .format(label, round(score.item(), 2)), color='red')
                ax.set_title('Image {}'.format(index))

    plt.show()


def show_labeled_image(image, boxes):
    """Show the image along with the specified boxes around detected objects.

    :param image: The image to plot.
    :type image: numpy.ndarray or torch.Tensor
    :param boxes: A torch tensor of size (N, 4) where N is the number
        of boxes to plot, or simply size 4 if N is 1.
    :type boxes: torch.Tensor

    **Example**::

        >>> from detecto.core import Model
        >>> from detecto.utils import read_image
        >>> from detecto.visualize import show_labeled_image

        >>> model = Model.load('model_weights.pth', ['tick', 'gate'])
        >>> image = read_image('image.jpg')
        >>> labels, boxes, scores = model.predict(image)
        >>> show_labeled_image(image, boxes)
    """

    fig, ax = plt.subplots(1)
    # If the image is already a tensor, convert it back to a PILImage
    if isinstance(image, torch.Tensor):
        image = transforms.ToPILImage()(image)
    ax.imshow(image)

    # Show a single box or multiple if provided
    if boxes.ndim == 1:
        boxes = boxes.view(1, 4)

    # Plot each box
    for box in boxes:
        width, height = (box[2] - box[0]).item(), (box[3] - box[1]).item()
        initial_pos = (box[0].item(), box[1].item())
        rect = patches.Rectangle(initial_pos,  width, height, linewidth=1,
                                 edgecolor='r', facecolor='none')

        ax.add_patch(rect)

    plt.show()
